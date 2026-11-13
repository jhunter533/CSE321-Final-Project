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
- Flask
- requests
- dotenv
- beautifulsoup4

### Environment Variables
### Populate the Database
The database is already populated and provided in `nmt_scheduler.db`. To repopulate the database after deleting any existing one run:
```bash
python main.py --term 202730
```
### Start the Backend
## REST Endpoints and Agent Tools
## Agent Implementation
## Database Scripts
`sql/schema.sql` contains all sql code run the creates the project schema. This file will not work properly outside of python as it requires the course data to exist which is only true if in the python files.

`sql/sample_session.sql` inserts sample schedule/session data for testing.
`nmt_scheduler.db` is included with this project containing populated data and all tables.
## Team Contributions
### Jessica Hunter
Implemented the course data and scheduling backend. Created the NMT Banweb scraper and parser, designed and populated the SQLite schema for courses, sections, meetings, instructors, and education requirements, schedules, and agent logs. Implemented schedule persistence logic. Implemented course-search,conflict-checking, and add-to-schedule service functions that directly deal with the database.

### Francisco Alejos
## AI Assistance
ChatGPT was used during development to ensure database design made sense and for occasional bug fixing with sql code and parsing integration. All suggestions were reviewed, modified, and tested before any inclusion in the project.
