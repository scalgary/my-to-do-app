const state = { sort_by: "due_date", order: "asc" };
const $ = (id) => document.getElementById(id);

function buildQuery() {
  const p = new URLSearchParams();
  for (const k of ["title", "tag", "done", "due_from", "due_to"]) {
    const v = $(k).value.trim();
    if (v) p.set(k, v);
  }
  p.set("sort_by", state.sort_by);
  p.set("order", state.order);
  return p.toString();
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

async function load() {
  const res = await fetch("/tasks?" + buildQuery());
  const tasks = await res.json();
  const body = $("tasks-body");
  body.replaceChildren();
  $("empty").hidden = tasks.length > 0;

  for (const t of tasks) {
    const tr = document.createElement("tr");
    if (t.done) tr.classList.add("done");

    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = t.done;
    box.disabled = t.done;
    box.setAttribute("aria-label", "Mark " + t.title + " as done");
    box.addEventListener("change", async () => {
      await fetch(`/tasks/${t.id}/done`, { method: "PATCH" });
      load();
    });
    const first = document.createElement("td");
    first.appendChild(box);

    tr.append(first, cell(t.title), cell(t.tag), cell(t.due_date), cell(t.id));
    body.appendChild(tr);
  }

  document.querySelectorAll("th").forEach((th) => {
    const key = th.querySelector("button").dataset.sort;
    th.setAttribute(
      "aria-sort",
      key === state.sort_by
        ? state.order === "asc"
          ? "ascending"
          : "descending"
        : "none",
    );
  });
}

document.querySelectorAll("th button").forEach((btn) => {
  btn.addEventListener("click", () => {
    const key = btn.dataset.sort;
    if (state.sort_by === key) {
      state.order = state.order === "asc" ? "desc" : "asc";
    } else {
      state.sort_by = key;
      state.order = "asc";
    }
    load();
  });
});

$("filters").addEventListener("input", load);
$("filters").addEventListener("reset", () => setTimeout(load, 0));

$("new-template").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    title: $("t-title").value.trim(),
    tag: $("t-tag").value.trim(),
    frequency: $("t-frequency").value,
    start_date: $("t-start").value,
    end_date: $("t-end").value || null,
  };
  const res = await fetch("/templates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  $("message").textContent = res.ok
    ? "Task added."
    : "Could not add the task. Check the dates.";
  if (res.ok) {
    e.target.reset();
    load();
  }
});

load();
