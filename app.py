import os
import sqlite3
import uuid
import database
import tools
import agent
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session, render_template

# Load .env file into Python environment
load_dotenv()

# Initialize the Flask application and configure secret key and database location
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")
DB_PATH = os.environ.get("DB_PATH", "nmt_scheduler.db")

# Create a database connection
def getConnection():
    return database.connect(DB_PATH)

# Makes sure that every browser session has a unique identifier
def ensureSession():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())

    return session["sid"]

# Create a custom jinja template filter
@app.template_filter("hhmm")
def hhmm(minutes):
    # Meeting times are stored as minutes after midnight
    if minutes is None:
        return "TBA"
    return f"{minutes // 60:02d}:{minutes % 60:02d}"

# Create a reusable way for the API endpoints to execute backend tools
def handleTool(name, args):
    # Get the browser session ID
    sid = session.get("sid")

    if not sid:
        return jsonify(success=False, error="Not logged in"), 401

    # Establish database connection
    connection = getConnection()

    try:
        # Get schedule associated with the session ID
        scheduleID = database.get_or_create_schedule(connection, sid)

        # Execute the requested tool and commit database changes
        result = tools.runTool(connection, scheduleID, name, args)
        connection.commit()

        # Return the result dictionary as a JSON
        return jsonify(result), (200 if result.get("success") else 400)
    # Handle validation errors from tool.py
    except tools.ValidationError as e:
        connection.rollback()
        return jsonify(success=False, error=str(e)), 400
    # Handle database errors
    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("database error in %s", name)
        return jsonify(success=False, error="Database error"), 500
    # Regardless, close the connection
    finally:
        connection.close()

# Creat course search API, obtain query parameter, then execute tool
@app.get("/api/tools/search_courses")
def APIsearchCourses():
    return handleTool("search_courses", {"query": request.args.get("query")})

# Create conflict checking API endpoint, get JSON request body, then execute tool
@app.post("/api/tools/check_conflicts")
def APIcheckConflicts():
    return handleTool("check_conflicts", request.get_json(silent=True) or {})

# Create the get schedule API, and then execute
@app.get("/api/tools/get_schedule")
def APIgetSchedule():
    return handleTool("get_schedule", {})

# Create the add to schedule API endpoint, retrieve submitted section ID, then execute tool
@app.post("/api/tools/add_to_schedule")
def APIaddToSchedule():
    return handleTool("add_to_schedule", request.get_json(silent=True) or {})

# Create the AI Agent form options
def getFormOptions(connection):
    # Obtain the requirements and course subjects
    requirements = [{"code": row[0], "name": row[1]} for row in connection.execute("SELECT code, name FROM Requirement ORDER BY code")]
    subjects = [row[0] for row in connection.execute("SELECT DISTINCT subject FROM Course ORDER BY subject")]

    return requirements, subjects

# Creates the homepage for the web application
@app.get("/")
def index():
    return agentPage()

# Creates the /agent page and allows it to get both GET/POST requests
@app.route("/agent", methods=["GET", "POST"])
def agentPage():
    # ensure session browser exists and connect to database
    sid = ensureSession()
    connection = getConnection()
    
    try:
        # get student schedule
        scheduleID = database.get_or_create_schedule(connection, sid)
        connection.commit()

        # Get the form options and create the page dictionary, response and results are none because student has not submitted anything
        requirements, subjects = getFormOptions(connection)
        page = {"requirements": requirements, "subjects": subjects, "response": None, "results": None}

        # Check if the student submitted the form
        if request.method == "POST":
            # get the values and validate them before they go anywhere
            try: 
                query = tools.cleanQuery(connection, request.form.get("requirement_section"))
                avoidDay = tools.cleanAvoidDay(request.form.get("avoid_day"))
            except tools.ValidationError as e:
                page["response"] = f"Error: {e}"
                return render_template("agent.html", **page), 400

            # Create the AI agent's goal
            goal = f"Find sections for {query} that fit the current schedule."
            if avoidDay:
                goal += f" I do not want classes on {avoidDay}."

            # send gaol to openRouter and gets the agent's response
            try:
                outcome = agent.runAgent(connection, sid, scheduleID, goal)
            except agent.AgentError as e:
                page["response"] = f"Agent error: {e}"
                return render_template("agent.html", **page), 502

            # apply the scheduling constraints in order to only display the valid courses
            tools.applyConstraints(connection, scheduleID, outcome["tool_results"], avoidDay)

            # Prepare the response for the HTML template
            page["response"] = outcome["message"] or "The agent ran the following tools:"
            page["results"] = outcome["tool_results"]

        return render_template("agent.html", **page)
    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("database error from /agent")
        return "Database error", 500
    finally:
        connection.close()
