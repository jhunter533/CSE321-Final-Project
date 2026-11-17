let ALL_SECTIONS = [];
let SCHEDULED_IDS = new Set();

function normalize(value) {
    return String(value ?? "").toUpperCase().replace(/AREA\s+(\d+)/g,"AREA$1").replace(/\s+/g," ").trim();
}

function formatTime(minutes) {
    if (minutes === null || minutes === undefined) {
        return "TBA";
    }
    const value = Number(minutes);
    const hour24 = Math.floor(value / 60);
    const minute = value % 60;
    const suffix = hour24 >= 12 ? "PM" : "AM";

    let hour = hour24 % 12;
    if (hour === 0) {
        hour = 12;
    }
    return (
        `${hour}:`
        +
        `${String(minute).padStart(2, "0")} `
        +
        `${suffix}`
    );
}

function formatDays(days) {
    if (!days) {
        return "Days TBA";
    }
    const names = {
        M: "Mon",
        T: "Tue",
        W: "Wed",
        R: "Thu",
        F: "Fri",
        S: "Sat",
        U: "Sun"
    };
    const output = [];

    for (const code of String(days).toUpperCase()) {
        if (names[code]) {
            output.push(
                names[code]
            );
        }
    }
    return (output.length > 0 ? output.join("/") : days);
}


function sectionSearchText(section) {
    const meetings =(section.meetings|| []).map(
        meeting =>
            [
                meeting.days,
                meeting.location,
                meeting.meeting_type,
                ...(
                    meeting.instructors || []
                )
            ].join(" ")
    ).join(" ");
    return normalize(
        [
            section.subject,
            section.course_number,
            section.section_number,
            section.title,
            section.crn,

            `${section.subject} `
            +
            `${section.course_number}`,

            `${section.subject} `
            +
            `${section.course_number}-`
            +
            `${section.section_number}`,

            meetings
        ].join(" ")
    );
}

function matchesSearch(section,query) {
    const normalized = normalize(query);
    if (!normalized) {
        return true;
    }
    if (normalized.startsWith("AREA")) {
        return (Array.isArray(section._areas) && section._areas.includes(normalized));
    }
    const haystack = sectionSearchText(section);

    return normalized
        .split(" ")
        .every(
            term =>
                haystack.includes(
                    term
                )
        );
}

function createMeetingElements(section) {
    const container = document.createElement("div");
    container.className = "meeting-list";
    const meetings = section.meetings || [];
    if (meetings.length === 0) {
        const row = document.createElement("div");
        row.className ="meeting-row";
        row.textContent ="Meeting information TBA";
        container.appendChild(row);
        return container;
    }

    for (const meeting of meetings) {
        const row = document.createElement("div");

        row.className = "meeting-row";
        const schedule = document.createElement("div");
        schedule.className = "meeting-schedule";
        if (meeting.meeting_type) {
            const type = document.createElement("span");
            type.className = "meeting-type";
            type.textContent = meeting.meeting_type;
            schedule.appendChild(type);
        }
        const time =document.createElement("span");
        time.className = "meeting-time";

        const timeText =
            (meeting.start_time === null || meeting.end_time === null) ? "Time TBA": (`${formatTime(meeting.start_time)}`+"–"+`${formatTime(meeting.end_time)}`);

        time.textContent = `${formatDays(meeting.days)} · ` + `${timeText}`;
        schedule.appendChild(time);

        const instructor = document.createElement("div");
        instructor.className ="meeting-instructor";
        const instructors = meeting.instructors || [];
        instructor.textContent =
            instructors.length > 0
                ? instructors.join(", ")
                : "Instructor TBA";
        row.appendChild(schedule);

        row.appendChild(instructor);

        container.appendChild(row);
    }
    return container;
}

function createCourseCard(section) {
    const card =
        document.createElement(
            "article"
        );

    card.className =
        "course-card";

    if (SCHEDULED_IDS.has(section.section_id)) {
        card.classList.add(
            "scheduled"
        );
    }

    const topRow =
        document.createElement(
            "div"
        );

    topRow.className = "course-top-row";

    const title = document.createElement("h3");
    title.className = "course-title";

    title.textContent = section.title || "Untitled Course";
    const code =
        document.createElement(
            "div"
        );
    code.className ="course-code";

    code.textContent =
        `${section.subject} `
        +
        `${section.course_number}-`
        +
        `${section.section_number}`;
    topRow.appendChild(title);
    topRow.appendChild(code);

    const meta =
        document.createElement(
            "div"
        );
    meta.className ="course-meta";
    const values = [
        `CRN ${section.crn}`
    ];

    if (section.credit_hours !== null && section.credit_hours !== undefined) {
        values.push(
            `${section.credit_hours} `
            +
            (
                Number(
                    section.credit_hours
                ) === 1
                    ? "credit"
                    : "credits"
            )
        );
    }
    meta.textContent =values.join(" · ");
    const actions = document.createElement("div");
    actions.className = "course-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "add-button";
    if (SCHEDULED_IDS.has(section.section_id)) {
        button.textContent ="Added";
        button.disabled =true;
    } else {
        button.textContent = "Add to Schedule";
        button.addEventListener(
            "click",
            async () => {
                button.disabled =
                    true;
                await addSection(
                    section.section_id
                );
            }
        );
    }
    actions.appendChild(button);
    card.appendChild(topRow);
    card.appendChild(meta);
    card.appendChild(
        createMeetingElements(
            section
        )
    );
    card.appendChild(actions);

    return card;
}

function renderSearchResults() {
    const input =
        document.getElementById(
            "course-search"
        );
    const results =
        document.getElementById(
            "course-results"
        );
    const count =
        document.getElementById(
            "result-count"
        );
    const matching =
        ALL_SECTIONS.filter(
            section =>
                matchesSearch(
                    section,
                    input.value
                )
        );
    results.innerHTML ="";
    count.textContent =`${matching.length} results`;

    if (matching.length === 0) {
        const message = document.createElement("p");
        message.className = "empty-message";
        message.textContent ="No matching sections.";
        results.appendChild(message);
        return;
    }

    for (const section of matching) {
        results.appendChild(
            createCourseCard(
                section
            )
        );
    }
}

function createScheduleCard(section) {
    const card =document.createElement("article");
    card.className ="schedule-card";
    const information = document.createElement("div");

    const title = document.createElement("h3");
    title.className = "schedule-card-title";
    title.textContent = section.title;

    const code =document.createElement("div");
    code.className = "schedule-card-code";
    code.textContent =
        `${section.subject} `
        +
        `${section.course_number}-`
        +
        `${section.section_number}`;

    const meetings = document.createElement("div");
    meetings.className = "schedule-meetings";
    for (const meeting of section.meetings || []) {
        const row = document.createElement("div");
        row.className = "schedule-meeting";

        row.textContent =
            `${formatDays(meeting.days)} · `
            +
            (
                meeting.start_time === null
                ||
                meeting.end_time === null

                    ? "Time TBA"

                    : (
                        `${formatTime(meeting.start_time)}`
                        +
                        "–"
                        +
                        `${formatTime(meeting.end_time)}`
                    )
            )
            +
            (
                meeting.location
                    ? ` · ${meeting.location}`
                    : ""
            );
        meetings.appendChild(row);
    }
    information.appendChild(title);
    information.appendChild(code);
    information.appendChild(meetings);
    const removeButton = document.createElement("button");

    removeButton.type ="button";
    removeButton.className ="remove-button";
    removeButton.textContent ="Remove";
    removeButton.addEventListener(
        "click",
        async () => {
            await removeSection(
                section.section_id
            );
        }
    );

    card.appendChild(information);
    card.appendChild(removeButton);
    return card;
}
async function refreshSchedule() {
    const response = await fetch("/api/tools/get_schedule");

    const data =await response.json();
    const container = document.getElementById("schedule-results");
    container.innerHTML = "";
    if (!response.ok || !data.success) {
        container.innerHTML =
            `<p class="empty-message">
                Could not load schedule.
            </p>`;

        return;
    }
    SCHEDULED_IDS =
        new Set(data.sections.map(
            section =>
                section.section_id
            )
        );

    if (data.sections.length === 0) {
        container.innerHTML =
            `<p class="empty-message">
                Your schedule is empty.
            </p>`;
        renderSearchResults();
        return;
    }
    for (const section of data.sections) {
        container.appendChild(createScheduleCard(section));
    }
    renderSearchResults();
}
async function addSection(sectionID) {
    const response =
        await fetch(
            "/api/tools/add_to_schedule",
            {
                method:
                    "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(
                        {
                            section_id:
                                sectionID
                        }
                    )
            }
        );
    const data = await response.json();
    if (!response.ok || !data.success) {
        alert(data.error || "Could not add section.");
        return;
    }
    await refreshSchedule();
}

async function removeSection(sectionID) {
    const response =
        await fetch(
            "/api/remove_from_schedule",
            {
                method:
                    "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(
                        {
                            section_id:
                                sectionID
                        }
                    )
            }
        );
    const data = await response.json();
    if (!response.ok || !data.success) {
        alert(
            data.error
            ||
            "Could not remove section."
        );
        return;
    }
    await refreshSchedule();
}

async function loadAllSections() {
    const sectionMap = new Map();
    for (const subject of window.NMT_SUBJECTS || []) {
        const response =
            await fetch(
                "/api/tools/search_courses"
                +
                "?query="
                +
                encodeURIComponent(
                    subject
                )
            );

        const data = await response.json();

        if (!response.ok || !data.success) {
            continue;
        }

        for (const section of data.sections) {
            section._areas = section._areas || [];
            sectionMap.set(section.section_id,section);
        }
    }

    for (const area of window.NMT_REQUIREMENTS || []) {
        const response =
            await fetch(
                "/api/tools/search_courses"
                +
                "?query="
                +
                encodeURIComponent(
                    area
                )
            );
        const data = await response.json();
        if (!response.ok || !data.success) {
            continue;
        }
        for (const section of data.sections) {
            const stored = sectionMap.get(section.section_id);
            if (!stored) {
                continue;
            }
            if (!stored._areas.includes(area)) {
                stored._areas.push(area);
            }
        }
    }
    ALL_SECTIONS =Array.from(sectionMap.values());
    ALL_SECTIONS.sort(
        (
            a,
            b
        ) => {
            const aKey =
                `${a.subject} `
                +
                `${a.course_number} `
                +
                `${a.section_number}`;

            const bKey =
                `${b.subject} `
                +
                `${b.course_number} `
                +
                `${b.section_number}`;

            return aKey.localeCompare(
                bKey
            );
        }
    );
}

document.addEventListener(
    "DOMContentLoaded",
    async () => {
        const input = document.getElementById("course-search");
        const clear = document.getElementById("clear-search");
        input.addEventListener("input",renderSearchResults);
        clear.addEventListener(
            "click",
            () => {
                input.value = "";
                renderSearchResults();
                input.focus();
            }
        );
        try {
            await Promise.all(
                [
                    loadAllSections(),
                    refreshSchedule(),
                ]
            );
            renderSearchResults();
        } catch (error) {
            console.error(error);
            document.getElementById("course-results").innerHTML =
                `<p class="empty-message">
                    Course data could not be loaded.
                </p>`;
        }
    }
);
