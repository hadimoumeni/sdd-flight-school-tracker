// Flight School Ops UI: static page that calls both services from the browser.
// Service URLs come from config.js, which the CD pipeline writes at deploy time.

const MAINTENANCE = { name: "Maintenance", url: window.APP_CONFIG.maintenanceUrl };
const SCHEDULING = { name: "Scheduling", url: window.APP_CONFIG.schedulingUrl };

// A cold start (container waking up, database resuming) can take a while, but a
// request must never hang: after this long we give up and show a clear message.
const TIMEOUT_MS = 15000;

class ApiError extends Error {}

// Every call to a service goes through here.
// - a timeout, network error or 502/503/504 means the service is down or still starting
// - any other error shows the service's own message ({"error": "..."})
async function api(service, path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response;
  try {
    response = await fetch(service.url + path, {
      ...options,
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });
  } catch {
    throw new ApiError(unavailable(service));
  } finally {
    clearTimeout(timer);
  }

  const body = await response.json().catch(() => null);
  if ([502, 503, 504].includes(response.status) && !body?.error) {
    throw new ApiError(unavailable(service));
  }
  if (!response.ok) {
    throw new ApiError(body?.error ?? `${service.name} returned HTTP ${response.status}`);
  }
  return body;
}

function unavailable(service) {
  return `${service.name} is starting up or unavailable. Wait a moment and press Retry.`;
}

function post(service, path, data) {
  return api(service, path, { method: "POST", body: JSON.stringify(data ?? {}) });
}

// ---------- small DOM helpers (textContent only, so user input is never run as HTML) ----------

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function row(...cells) {
  const tr = document.createElement("tr");
  for (const cell of cells) {
    const td = document.createElement("td");
    td.append(cell instanceof Node ? cell : String(cell ?? ""));
    tr.append(td);
  }
  return tr;
}

function emptyRow(columns, text) {
  const td = el("td", text, "note");
  td.colSpan = columns;
  const tr = document.createElement("tr");
  tr.append(td);
  return tr;
}

function options(select, items, label) {
  select.replaceChildren(...items.map((item) => {
    const option = el("option", label(item));
    option.value = item.id;
    return option;
  }));
}

function showTime(iso) {
  return iso ? iso.slice(0, 16).replace("T", " ") : "";
}

function hours(value) {
  return Number(value).toFixed(1);
}

// ---------- messages ----------

function showMessage(text, isError = false, retry = null) {
  const box = el("div", text, isError ? "flash error" : "flash");
  if (retry) {
    const button = el("button", "Retry");
    button.type = "button";
    button.style.marginLeft = "0.5rem";
    button.addEventListener("click", retry);
    box.append(button);
  }
  document.getElementById("messages").replaceChildren(box);
}

function clearMessages() {
  document.getElementById("messages").replaceChildren();
}

// Submit a form as JSON, then reload the current page; errors are shown, not thrown.
function onSubmit(formId, send) {
  const form = document.getElementById(formId);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    try {
      await send(Object.fromEntries(new FormData(form)));
      form.reset();
      clearMessages();
      await render();
    } catch (err) {
      showMessage(err.message, true);
    } finally {
      button.disabled = false;
    }
  });
}

// ---------- health bar ----------

async function showHealth() {
  const bar = document.getElementById("health");
  const parts = await Promise.all(
    [SCHEDULING, MAINTENANCE].map(async (service) => {
      try {
        await api(service, "/health");
        return [service.name, "up", "ok"];
      } catch {
        return [service.name, "down", "down"];
      }
    }),
  );
  bar.replaceChildren(
    ...parts.flatMap(([name, state, css], i) => [
      i ? " · " : "",
      `${name}: `,
      el("span", state, css),
    ]),
  );
}

// ---------- scheduling page ----------

async function renderScheduling() {
  // Scheduling data and the aircraft list come from different services. Load them
  // side by side so one being down does not hide the other's data.
  const [scheduling, aircraftResult] = await Promise.allSettled([
    Promise.all([
      api(SCHEDULING, "/lessons"),
      api(SCHEDULING, "/students"),
      api(SCHEDULING, "/instructors"),
    ]),
    api(MAINTENANCE, "/aircraft"),
  ]);

  const aircraft = aircraftResult.status === "fulfilled" ? aircraftResult.value : [];
  const tailNumbers = new Map(aircraft.map((a) => [a.id, a.tail_number]));
  const notice = document.getElementById("aircraft-notice");
  notice.hidden = aircraftResult.status === "fulfilled";
  notice.textContent =
    "Maintenance is unavailable: tail numbers are not shown and lessons cannot be booked or completed right now.";
  options(document.getElementById("aircraft-select"), aircraft, (a) =>
    a.airworthy ? a.tail_number : `${a.tail_number} (grounded)`,
  );

  const rows = document.getElementById("lesson-rows");
  if (scheduling.status === "rejected") {
    rows.replaceChildren(emptyRow(7, scheduling.reason.message));
    showMessage(scheduling.reason.message, true, render);
    return;
  }

  const [lessons, students, instructors] = scheduling.value;
  options(document.getElementById("student-select"), students, (s) => s.name);
  options(document.getElementById("instructor-select"), instructors, (i) => i.name);

  rows.replaceChildren(
    ...lessons.map((lesson) => {
      let action = "";
      if (lesson.status === "scheduled") {
        action = el("button", "Mark complete");
        action.addEventListener("click", () => completeLesson(lesson.id, action));
      }
      return row(
        lesson.student_name,
        lesson.instructor_name,
        tailNumbers.get(lesson.aircraft_id) ?? `aircraft #${lesson.aircraft_id}`,
        showTime(lesson.start_time),
        showTime(lesson.end_time),
        lesson.status,
        action,
      );
    }),
  );
  if (lessons.length === 0) rows.append(emptyRow(7, "No lessons yet."));
}

async function completeLesson(lessonId, button) {
  button.disabled = true;
  try {
    const result = await post(SCHEDULING, `/lessons/${lessonId}/complete`);
    showMessage(`Lesson completed: ${hours(result.hours)} flight hours logged.`);
    await render();
  } catch (err) {
    showMessage(err.message, true);
    button.disabled = false;
  }
}

onSubmit("book-form", (data) =>
  post(SCHEDULING, "/lessons", {
    ...data,
    student_id: Number(data.student_id),
    instructor_id: Number(data.instructor_id),
    aircraft_id: Number(data.aircraft_id),
  }),
);
onSubmit("student-form", (data) => post(SCHEDULING, "/students", data));
onSubmit("instructor-form", (data) => post(SCHEDULING, "/instructors", data));

// ---------- maintenance page ----------

async function renderMaintenance() {
  const aircraftRows = document.getElementById("aircraft-rows");
  const squawkRows = document.getElementById("squawk-rows");
  let aircraft;
  let squawks;
  try {
    [aircraft, squawks] = await Promise.all([
      api(MAINTENANCE, "/aircraft"),
      api(MAINTENANCE, "/squawks"),
    ]);
  } catch (err) {
    aircraftRows.replaceChildren(emptyRow(5, err.message));
    squawkRows.replaceChildren();
    showMessage(err.message, true, render);
    return;
  }

  options(document.getElementById("squawk-aircraft-select"), aircraft, (a) => a.tail_number);

  aircraftRows.replaceChildren(
    ...aircraft.map((a) =>
      row(
        a.tail_number,
        a.model,
        hours(a.total_hours),
        hours(a.total_hours - a.hours_at_last_inspection),
        a.airworthy ? el("span", "airworthy", "ok") : el("span", a.reason, "grounded"),
      ),
    ),
  );
  if (aircraft.length === 0) aircraftRows.append(emptyRow(5, "No aircraft yet."));

  squawkRows.replaceChildren(
    ...squawks.map((s) => {
      const resolve = el("button", "Resolve");
      resolve.addEventListener("click", async () => {
        resolve.disabled = true;
        try {
          await post(MAINTENANCE, `/squawks/${s.id}/resolve`);
          await render();
        } catch (err) {
          showMessage(err.message, true);
          resolve.disabled = false;
        }
      });
      return row(s.tail_number, s.description, s.severity, showTime(s.reported_at), resolve);
    }),
  );
  if (squawks.length === 0) squawkRows.append(emptyRow(5, "No open squawks."));
}

onSubmit("aircraft-form", (data) => post(MAINTENANCE, "/aircraft", data));
onSubmit("squawk-form", (data) =>
  post(MAINTENANCE, "/squawks", { ...data, aircraft_id: Number(data.aircraft_id) }),
);

// ---------- navigation ----------

async function render() {
  const page = location.hash === "#maintenance" ? "maintenance" : "scheduling";
  for (const name of ["scheduling", "maintenance"]) {
    document.getElementById(name).hidden = name !== page;
    document.getElementById(`nav-${name}`).classList.toggle("active", name === page);
  }
  showHealth();
  await (page === "maintenance" ? renderMaintenance() : renderScheduling());
}

window.addEventListener("hashchange", () => {
  clearMessages();
  render();
});
render();
