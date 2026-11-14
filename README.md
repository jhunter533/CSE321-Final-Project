# CSE321-Final-Project
# NMT Scheduler
## Project Overview
NMT Scheduler is a web application for New Mexico Tech students to search available courses, build a semester schedule, check scheduling conflicts, and receive course suggestions using agentic AI.

For milestone 1, this application includes a relational SQLite database, session-based schedule states, REST tool endpoints, and a server-side AI connected to OpenRouter.
## Database and Schema
The project uses SQLite.

SQLite foreign key enforcement is enabled on every database.

Database file:
`nmt_scheduler.db`

Tables:
- `Course`- Catalog course information including subject, course number, and title.
- `Section` - Semester specific course sections and CRNs.
- `Meeting`- Meeting days, dates, times, locations, and types.
- `Instructor` - Unique instructor records.
- `MeetingInstructor` - Many-to-many relationship between meetings and instructors.
- `Requirement` - General education requirement areas.
- `RequirementSubject` - Maps requirement areas to subject codes.
- `RequirementIncludes` - Allows requirements to include other existing areas.
- `Schedule` - Stores one schedule associated with browser session.
- `ScheduleSection` - Many-to-many relationship between schedules and course sections.
- `AgentLog` - Records agent tool calls, including user/session ID, tool name, input, output, iteration, and timestamp.

Important relationships include:
- Course 1:N Section
- Section 1:N Meeting
- Meeting N:M Instructor through MeetingInstructor
- Requirement N:M subject codes through RequirementSubject
- Schedule N:M Section through ScheduleSection
- AgentLog may reference Schedule used by agent

## Session Model
The approved project proposal does not user permanent user accounts. Instead each browser  receives a unique Flask session UUID.  This is associated with one row in Schedule table. The user’s selected sections are stored in ScheduleSection.
## Running the Application
### Requirements
Python 3 and the following:
- flask
- requests
- python-dotenv
- beautifulsoup4

### Environment Variables
create a .env file with:
```
FLASK_SECRET_KEY=(Randomly generated string: "secrets.token_hex(32))"
OPENROUTER_API_KEY=(Key from openrouter.ai)
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
DB_PATH=nmt_scheduler.db
```

### Populate the Database
The database is already populated and provided in `nmt_scheduler.db`. To repopulate the database after deleting any existing one run:
```bash
python main.py --term 202730
```
### Start the Backend
Run the following commands in the repo folder:
```
python -m venv venv
source venv/Scripts/activate
pu -m pip install flask requests python-dotevn beautifulsoup4

flask run --debug
```

Open http://127.0.0.1:5000/agent.

## REST Endpoints and Agent Tools
| Servlet/Flask Route | URL | Method | Agent Tool |
|---|---|---|---|
| 'APIsearchCourses()' | '/api/tools/search_courses' | GET | 'search_courses' | 
| 'APIcheckConflicts()' | '/api/tools/check_conflicts' | POST | 'check_conflicts' |
| 'APIgetSchedule()' | '/api/tools/get_schedule' | GET | 'get_schedule' |
| 'APIaddToSchedule()' | '/api/tools/add_to_schedule' | POST | 'add_to_schedule' |

## Agent Implementation
1. Student Input: The student selects a Requirement or Subject and optionally chooses a day to avoid
2. LLM Request: Application sends the student's request as a goal to the AI agent through OpenRouter
3. Tool Selection: The AI requests the necessary tools to complete the goal
4. Tool Execution: The Flask backend validates the request args and executes the tools using the SQLite Database and the backend service functions
5. Conflict Filtering: The agent results are filtered to only include valid courses that won't conflict with the student's schedule and the goal sentence by the student
6. Display Results: The application displays the AI response on the webpage.

## Database Scripts
`sql/schema.sql` contains all sql code run the creates the project schema. This file will not work properly outside of python as it requires the course data to exist which is only true if in the python files.

`sql/sample_session.sql` inserts sample schedule/session data for testing.
`nmt_scheduler.db` is included with this project containing populated data and all tables.
## Team Contributions
### Jessica Hunter
Implemented the course data and scheduling backend. Created the NMT Banweb scraper and parser, designed and populated the SQLite schema for courses, sections, meetings, instructors, and education requirements, schedules, and agent logs. Implemented schedule persistence logic. Implemented course-search,conflict-checking, and add-to-schedule service functions that directly deal with the database.

### Francisco Alejos
Built the web and agent layers for the project. Wrote the Flask app with session identity and the JSON tool endpoints, which also includes input validation. Added server side conflict checking along with implementing the OpenRouter integration to have an operating AI agent. Extended the frontend to include the agent results and a functional scheduler that allows students to add classes.

## AI Assistance
ChatGPT was used during development to ensure database design made sense and for occasional bug fixing with sql code and parsing integration. All suggestions were reviewed, modified, and tested before any inclusion in the project.
