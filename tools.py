import database
import services

VALID_DAYS = {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}

AGENT_TOOLS = {"search_courses", "check_conflicts", "get_schedule"}
ALL_TOOLS = AGENT_TOOLS | {"add_to_schedule"}

# Custom exception for errors that are related to validation
class ValidationError(ValueError):
    pass

# cleanQuery validates the search query before the application searches the database
def cleanQuery(connection, value):
    # First, make sure query is actually valid
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Query is required. (Ex: AREA7 or PHYS)")

    # Uppercase to AREA7 or PHYS, then retrieve the requirement codes and subjects
    value = value.strip().upper()
    codes = {row[0] for row in connection.execute("SELECT code FROM Requirement")}
    subjects = {row[0] for row in connection.execute("SELECT DISTINCT subject FROM Course")}

    # Check if the input actually exists within the database
    if value not in codes | subjects:
        raise ValidationError("Unknown Requirement or Subject")

    return value

# Validates the section IDs
def cleanSectionID(value):
    # Check if the value is actually real and not a bool
    if isinstance(value, bool):
        raise ValidationError("Section ID must be a positive integer.")

    # Check if the value is a string and if it only contains digits, then convert to int
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())

    # Make sure that the ID is a positive integer
    if not isinstance(value, int) or value <= 0:
        raise ValidationError("Section ID must be a positive integer.")

    return value

# Validate optional day restrictions
def cleanAvoidDay(value):

    # If no restrictions, function returns an empty string
    if value in (None, ""):
        return ""

    # Check if value is a string and it is an actual valid day
    if not isinstance(value, str) or value.strip().capitalize() not in VALID_DAYS:
        raise ValidationError("Avoid Days must be a valid day (Ex: Monday)")

    return value.strip().capitalize()

# Central dispather that takes a request, figure out what tool is used, valid input, then make the calls
def runTool(connection, scheduleID, name, args):
    if name not in ALL_TOOLS:
        raise ValidationError("Unknown Tool")

    # Tool expects arguments to be a python dictionary
    if not isinstance(args, dict):
        raise ValidationError("Arguments must be a JSON object")

    # If statements for checking what tool to use
    if name == "search_courses":
        return services.search_courses(connection, cleanQuery(connection, args.get("query")))
    if name == "check_conflicts":
        return services.check_conflicts(connection, scheduleID, cleanSectionID(args.get("section_id")), cleanAvoidDay(args.get("avoid_day")))
    if name == "add_to_schedule":
        sectionID = cleanSectionID(args.get("section_id"))

        # Refuse to double book at once. The server decides, not the page
        check = services.check_conflicts(connection, scheduleID, sectionID, "")
        if not check.get("success"):
            return check
        if check.get("conflict"):
            return {"success": False, "error": "Time conflict: " + "; ".join(check["reasons"])}

        # Add the course if there are no conflicts
        return services.add_to_schedule(connection, scheduleID, sectionID)

    # if name does not match above tools, it is get_schedule
    sections = database.get_schedule(connection, scheduleID)

    # Loop through every section in the student's schedule
    for section in sections:
        rows = connection.execute(
            "SELECT days, start_time, end_time, location, meeting_type FROM Meeting WHERE section_id = ? ORDER BY meeting_id", (section["section_id"],)).fetchall()

        # Takes every meeting record from database and converts it into a dictionary
        section["meetings"] = [{"days": r[0], "start_time": r[1], "end_time": r[2], "location": r[3], "meeting_type": r[4]} for r in rows]

    # Return the schedule
    return {"success": True, "schedule_id": scheduleID, "sections": sections}

# Applies additional scheduling restrictions to the results returned by the AI agent
def applyConstraints(connection, scheduleID, results, avoidDay):

    # Obtain the sections in the students schedule
    onSchedule = {s["section_id"] for s in database.get_schedule(connection, scheduleID)}

    # Loop through the agent's tool results
    for result in results:
        output = result["output"]

        # if the tool called wasn't search_courses or the course search failed, then skip it
        if result["tool"] != "search_courses" or not output.get("success"):
            continue

        # Create a new list of acceptable courses
        kept = []

        # Check every suggested section
        for section in output["sections"]:

            # Skip if section is already in schedule
            if section["section_id"] in onSchedule:
                continue

            # If not, check if it conflicts with any times on the student's schedule
            check = services.check_conflicts(connection, scheduleID, section["section_id"], avoidDay)

            # If course is not in schedule and no conflicts rise, make it available
            if check.get("success") and not check.get("conflict"):
                kept.append(section)

        # Record how many sections were removed
        output["removed"] = len(output["sections"]) - len(kept)

        # Replace original search results with the available ones
        output["sections"] = kept
    
