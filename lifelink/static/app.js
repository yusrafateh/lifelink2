/* LifeLink front-end (VIEW). Talks only to the REST API. Uses textContent everywhere (XSS-safe). */
const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
let token = sessionStorage.getItem("token");
let me = null;
let pollTimer = null;

const $ = (sel) => document.querySelector(sel);
const show = (el, on = true) => el.classList.toggle("hidden", !on);

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  });
  children.flat().forEach((c) => node.append(c instanceof Node ? c : document.createTextNode(c ?? "")));
  return node;
}

function toast(msg, ok = true) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast " + (ok ? "ok" : "err");
  setTimeout(() => show(t, false), 3500);
}

async function api(path, method = "GET", body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (token) opts.headers.Authorization = "Bearer " + token;
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch("/api" + path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && token) logout();
    throw new Error(data.error || "Request failed");
  }
  return data;
}

const formData = (form) => Object.fromEntries(new FormData(form).entries());

/* ---------- auth ---------- */
function fillBloodSelects() {
  document.querySelectorAll(".bgSelect").forEach((s) => {
    s.replaceChildren(...BLOOD_GROUPS.map((g) => el("option", { value: g }, g)));
  });
}

function logout() {
  token = null; me = null;
  sessionStorage.removeItem("token");
  clearInterval(pollTimer);
  render();
}

async function boot() {
  fillBloodSelects();
  if (token) {
    try { me = await api("/me"); } catch { token = null; }
  }
  render();
}

function render() {
  ["authView", "donorView", "requesterView", "adminView"].forEach((id) => show($("#" + id), false));
  show($("#userbox"), !!me);
  if (!me) { show($("#authView")); return; }
  $("#whoami").textContent = `${me.name} (${me.role})`;
  show($("#" + me.role + "View"));
  clearInterval(pollTimer);
  if (me.role === "donor") { fillProfile(); loadNotifications(); pollTimer = setInterval(loadNotifications, 5000); }
  if (me.role === "requester") { loadMyRequests(); pollTimer = setInterval(loadMyRequests, 3000); }
  if (me.role === "admin") { loadAdmin(); pollTimer = setInterval(loadAdmin, 5000); }
}

document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
  show($("#loginForm"), b.dataset.tab === "login");
  show($("#registerForm"), b.dataset.tab === "register");
}));

$("#regRole").addEventListener("change", (e) => show($("#regBloodWrap"), e.target.value === "donor"));

$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const r = await api("/auth/login", "POST", formData(e.target));
    token = r.token; me = r.user;
    sessionStorage.setItem("token", token);
    render();
  } catch (err) { toast(err.message, false); }
});

$("#registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/auth/register", "POST", formData(e.target));
    toast("Registered! Please login.");
    e.target.reset();
    document.querySelector('.tab[data-tab="login"]').click();
  } catch (err) { toast(err.message, false); }
});

$("#logoutBtn").addEventListener("click", logout);

/* ---------- donor ---------- */
function fillProfile() {
  const f = $("#profileForm");
  ["name", "phone", "city", "blood_group", "last_donation"].forEach((k) => { f.elements[k].value = me[k] || ""; });
  f.elements.available.checked = !!me.available;
}

$("#profileForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(e.target);
  d.available = e.target.elements.available.checked;
  try { me = await api("/me", "PUT", d); toast("Profile saved."); fillProfile(); }
  catch (err) { toast(err.message, false); }
});

async function loadNotifications() {
  try {
    const list = await api("/notifications");
    const box = $("#notifList");
    if (!list.length) { box.replaceChildren(el("p", { class: "hint" }, "No requests for you right now.")); return; }
    box.replaceChildren(...list.map((n) => {
      const actions = [];
      if (n.status === "sent" && !["cancelled", "fulfilled"].includes(n.request_status)) {
        actions.push(
          el("button", { class: "btn small", onclick: () => respond(n.id, "accept") }, "Accept"), " ",
          el("button", { class: "btn small ghost", onclick: () => respond(n.id, "decline") }, "Decline"));
      }
      return el("div", { class: "item " + n.urgency },
        el("b", {}, `${n.blood_group} needed - ${n.hospital}, ${n.city}`),
        el("span", { class: "badge " + n.status }, n.status),
        el("span", { class: "badge " + n.request_status }, "request " + n.request_status),
        el("div", { class: "hint" }, n.message), el("div", {}, actions));
    }));
  } catch (err) { /* handled in api() */ }
}

async function respond(id, response) {
  try { const r = await api(`/notifications/${id}/respond`, "POST", { response }); toast(r.message); loadNotifications(); }
  catch (err) { toast(err.message, false); }
}
$("#refreshDonor").addEventListener("click", loadNotifications);

/* ---------- requester ---------- */
$("#requestForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const r = await api("/requests", "POST", formData(e.target));
    toast(r.message); loadMyRequests();
  } catch (err) { toast(err.message, false); }
});

async function loadMyRequests() {
  try {
    const list = await api("/requests/mine");
    const box = $("#myRequests");
    if (!list.length) { box.replaceChildren(el("p", { class: "hint" }, "No requests yet.")); return; }
    box.replaceChildren(...list.map((r) => {
      const donors = r.accepted_donors.map((d) =>
        el("div", { class: "donor-contact" }, `${d.name} (${d.blood_group}) - ${d.phone}`));
      const cancel = ["open", "pending", "matching"].includes(r.status)
        ? el("button", { class: "btn small ghost", onclick: () => cancelReq(r.id) }, "Cancel") : "";
      return el("div", { class: "item " + r.urgency },
        el("b", {}, `#${r.id} ${r.patient_name} - ${r.blood_group} x${r.units}`),
        el("span", { class: "badge " + r.status }, r.status),
        el("div", { class: "hint" }, `${r.hospital}, ${r.city} | donors notified: ${r.notified_count} | accepted: ${r.accepted_donors.length}`),
        donors, cancel);
    }));
  } catch (err) { /* handled */ }
}
async function cancelReq(id) {
  try { const r = await api(`/requests/${id}/cancel`, "POST"); toast(r.message); loadMyRequests(); }
  catch (err) { toast(err.message, false); }
}
$("#refreshReq").addEventListener("click", loadMyRequests);

/* ---------- admin ---------- */
function table(headers, rows) {
  return el("table", {}, el("tr", {}, headers.map((h) => el("th", {}, h))),
    rows.map((r) => el("tr", {}, r.map((c) => el("td", {}, c)))));
}

async function loadAdmin() {
  try {
    const [s, users, reqs] = await Promise.all([api("/admin/stats"), api("/admin/users"), api("/admin/requests")]);
    $("#statsGrid").replaceChildren(...Object.entries(s).map(([k, v]) =>
      el("div", { class: "stat" }, el("b", {}, String(v)), k.replaceAll("_", " "))));
    $("#adminUsers").replaceChildren(table(
      ["ID", "Name", "Email", "Role", "City", "Group", "Active", "Action"],
      users.map((u) => [u.id, u.name, u.email, u.role, u.city, u.blood_group || "-", u.is_active ? "yes" : "no",
        u.role === "admin" ? "-" : el("button", { class: "btn small ghost", onclick: () => toggleUser(u.id) }, u.is_active ? "Disable" : "Enable")])));
    $("#adminRequests").replaceChildren(table(
      ["ID", "Patient", "Group", "Units", "City", "Hospital", "Urgency", "Status", "Notified"],
      reqs.map((r) => [r.id, r.patient_name, r.blood_group, r.units, r.city, r.hospital, r.urgency, r.status, r.notified_count])));
  } catch (err) { /* handled */ }
}
async function toggleUser(id) {
  try { await api(`/admin/users/${id}/toggle`, "POST"); loadAdmin(); } catch (err) { toast(err.message, false); }
}
$("#refreshAdmin").addEventListener("click", loadAdmin);

boot();
