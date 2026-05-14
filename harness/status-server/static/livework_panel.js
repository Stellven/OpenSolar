/* Solar Harness — Live Work Panel JS
   Vanilla fetch + DOM, no frameworks. */

(function () {
  var BASE = "/api";

  function $(id) { return document.getElementById(id); }

  function setContent(cardId, html) {
    var el = $(cardId);
    if (!el) return;
    var content = el.querySelector(".card-content");
    if (content) content.innerHTML = html;
  }

  function setSourceTs(cardId, ts) {
    var el = $(cardId);
    if (!el) return;
    var tag = el.querySelector(".source-tag");
    if (tag && ts) tag.textContent = "\u6765\u6e90: events.jsonl@" + ts;
  }

  function formatIdle(data) {
    if (data.is_idle) {
      return '<span style="color:#ffa726">No active work</span> (idle since ' +
        (data.idle_since || "unknown") + ")";
    }
    var panes = data.active_panes || [];
    return "Active panes: " + (panes.length ? panes.join(", ") : "unknown") +
      " | queue: " + data.queue_depth;
  }

  function formatNextStep(data) {
    var nodes = data.nodes || [];
    var lines = ["Phase: " + (data.phase || "unknown"),
      "Next: " + (data.next_action || "unknown")];
    nodes.forEach(function (n) {
      lines.push("  " + n.id + " [" + n.status + "] " + (n.goal || ""));
    });
    return lines.join("<br>");
  }

  function formatDeadlocks(data) {
    var alerts = data.active_deadlocks || [];
    if (!alerts.length) return "No deadlocks detected";
    return alerts.map(function (a) {
      return "Pane " + a.pane_id + " stuck " + a.elapsed_seconds + "s";
    }).join("<br>");
  }

  function formatEventsTail(data) {
    if (!data || !data.length) return "No recent events";
    return data.slice(-10).map(function (e) {
      var ts = e.ts || e.timestamp || "?";
      var type = e.type || e.event || "?";
      return '<div class="event-line">' + ts + " " + type + "</div>";
    }).join("");
  }

  function fetchJSON(path, cb) {
    fetch(BASE + path)
      .then(function (r) { return r.json(); })
      .then(cb)
      .catch(function () { cb(null); });
  }

  function refresh() {
    fetchJSON("/idle-state", function (d) {
      setContent("no-active-work-card", d ? formatIdle(d) : "unknown");
      if (d && d.last_heartbeat_ts) setSourceTs("no-active-work-card", d.last_heartbeat_ts);
    });

    fetchJSON("/sprints/_default/next-step", function (d) {
      setContent("role-next-step-card", d ? formatNextStep(d) : "unknown");
    });

    fetchJSON("/deadlock-alerts", function (d) {
      setContent("deadlock-alerts-card", d ? formatDeadlocks(d) : "unknown");
      if (d && d.checked_at) setSourceTs("deadlock-alerts-card", d.checked_at);
    });

    fetchJSON("/events/tail", function (d) {
      setContent("events-tail-card", d ? formatEventsTail(d) : "unknown");
    });
  }

  refresh();
  setInterval(refresh, 30000);
})();
