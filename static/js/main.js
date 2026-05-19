/**
 * PeerLearn — main.js  (complete rewrite)
 * Fixes: modal auto-open, 404 upvote, avatar in lists, notif dropdown,
 *        friend requests panel, status persistence, member count updates.
 * New:   light/dark theme toggle, colour swatch picker.
 */
"use strict";

/* ═══════════════════════════════════════════════════════════════════
   1. UTILITIES
═══════════════════════════════════════════════════════════════════ */
async function apiFetch(url, options = {}) {
  const merged = {
    headers: {
      "Content-Type":    "application/json",
      "X-CSRFToken":     CSRF_TOKEN,
      "X-Requested-With":"XMLHttpRequest",
    },
    credentials: "same-origin",
    ...options,
  };
  if (options.headers) Object.assign(merged.headers, options.headers);
  const res  = await fetch(url, merged);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function escHtml(str) {
  return String(str ?? "")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}

function showToast(message, type = "info") {
  let c = document.getElementById("toastContainer");
  if (!c) {
    c = document.createElement("div");
    c.id = "toastContainer";
    c.style.cssText = "position:fixed;top:72px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;min-width:280px;max-width:360px";
    document.body.appendChild(c);
  }
  const t = document.createElement("div");
  t.className = `flash flash--${type}`;
  t.innerHTML = `${escHtml(message)}<button class="flash-close" onclick="this.parentElement.remove()">×</button>`;
  c.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

function debounce(fn, ms = 300) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
}

function setButtonLoading(btn, loading) {
  if (!btn) return;
  if (loading) {
    btn.dataset.originalHtml = btn.innerHTML;
    btn.innerHTML = `<span class="spinner" style="width:14px;height:14px;border-width:2px;display:inline-block"></span>`;
    btn.disabled = true;
  } else {
    btn.innerHTML = btn.dataset.originalHtml || btn.innerHTML;
    btn.disabled = false;
  }
}

/* ═══════════════════════════════════════════════════════════════════
   2. THEME TOGGLE (light / dark)
═══════════════════════════════════════════════════════════════════ */
const THEME_KEY = "pl_theme";

function applyTheme(theme) {
  document.getElementById("htmlRoot").setAttribute("data-theme", theme);
  const icon = document.getElementById("themeIcon");
  if (icon) icon.className = theme === "dark" ? "bi bi-moon-fill" : "bi bi-sun-fill";
  localStorage.setItem(THEME_KEY, theme);
}

(function initTheme() {
  const saved = localStorage.getItem(THEME_KEY) || "dark";
  applyTheme(saved);
})();

document.getElementById("themeToggleBtn")?.addEventListener("click", () => {
  const current = document.getElementById("htmlRoot").getAttribute("data-theme") || "dark";
  applyTheme(current === "dark" ? "light" : "dark");
});

/* ═══════════════════════════════════════════════════════════════════
   3. HAMBURGER SIDEBAR TOGGLE
═══════════════════════════════════════════════════════════════════ */
const hamburgerBtn = document.getElementById("hamburgerBtn");
const appLayout    = document.getElementById("appLayout");

hamburgerBtn?.addEventListener("click", () => {
  const collapsed = appLayout.classList.toggle("sidebar-collapsed");
  hamburgerBtn.setAttribute("aria-expanded", String(!collapsed));
  localStorage.setItem("sidebarCollapsed", collapsed ? "1" : "0");
});

if (localStorage.getItem("sidebarCollapsed") === "1") {
  appLayout?.classList.add("sidebar-collapsed");
}

/* ═══════════════════════════════════════════════════════════════════
   4. PROFILE DROPDOWN
═══════════════════════════════════════════════════════════════════ */
const profileAvatarBtn = document.getElementById("profileAvatarBtn");
const profileDropdown  = document.getElementById("profileDropdown");

profileAvatarBtn?.addEventListener("click", e => {
  e.stopPropagation();
  profileDropdown.classList.toggle("open");
  document.getElementById("notifDropdown")?.classList.remove("open");
});

document.addEventListener("click", e => {
  if (!profileDropdown?.contains(e.target) && e.target !== profileAvatarBtn) {
    profileDropdown?.classList.remove("open");
  }
  if (!document.getElementById("notifWrapper")?.contains(e.target)) {
    document.getElementById("notifDropdown")?.classList.remove("open");
  }
});

document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    profileDropdown?.classList.remove("open");
    document.getElementById("notifDropdown")?.classList.remove("open");
    closeFriendModal();
  }
});

/* ═══════════════════════════════════════════════════════════════════
   5. NOTIFICATIONS / FRIEND REQUESTS DROPDOWN
═══════════════════════════════════════════════════════════════════ */
document.getElementById("notifBtn")?.addEventListener("click", e => {
  e.stopPropagation();
  document.getElementById("notifDropdown").classList.toggle("open");
  profileDropdown?.classList.remove("open");
});

/* ═══════════════════════════════════════════════════════════════════
   6. STATUS TOGGLE — persists via Redis, re-reads server value
═══════════════════════════════════════════════════════════════════ */
// Initialise the nav dot from the server-rendered value
(function initStatusDot() {
  const dot = document.getElementById("myStatusDot");
  if (dot && typeof MY_STATUS_INIT !== "undefined") {
    dot.className = `status-dot status-dot--${MY_STATUS_INIT}`;
  }
})();

document.querySelectorAll(".status-toggle-btn").forEach(btn => {
  btn.addEventListener("click", async () => {
    const status = btn.dataset.status;
    try {
      const data = await apiFetch("/accounts/status/set/", {
        method: "POST",
        body: JSON.stringify({ status }),
      });
      // Update nav dot with the resolved status from server
      const dot = document.getElementById("myStatusDot");
      if (dot && data.resolved) {
        dot.className = `status-dot status-dot--${data.resolved}`;
      }
      // Highlight active button
      document.querySelectorAll(".status-toggle-btn").forEach(b => b.classList.remove("pd-item--active"));
      btn.classList.add("pd-item--active");
      showToast("Status updated.", "success");
      profileDropdown?.classList.remove("open");
    } catch (e) {
      showToast(e.message, "error");
    }
  });
});

/* ═══════════════════════════════════════════════════════════════════
   7. GLOBAL SEARCH
═══════════════════════════════════════════════════════════════════ */
const globalSearch   = document.getElementById("globalSearch");
const searchDropdown = document.getElementById("searchDropdown");

function renderSearchResults(data) {
  const { users=[], channels=[], discussions=[], messages=[] } = data;
  const total = users.length + channels.length + discussions.length + messages.length;

  if (total === 0) {
    searchDropdown.innerHTML = `<div class="search-no-results">No results found</div>`;
  } else {
    let html = "";
    if (users.length) {
      html += `<div class="search-category">People</div>`;
      users.forEach(u => {
        const avatarHtml = u.avatar_url
          ? `<img src="${escHtml(u.avatar_url)}" style="width:28px;height:28px;border-radius:50%;object-fit:cover">`
          : `<div class="search-result-avatar" style="background:${u.avatar_color}">${escHtml(u.initial)}</div>`;
        html += `<div class="search-result-item" onclick="window.location='/accounts/profile/${escHtml(u.username)}/'">
          ${avatarHtml}
          <div><div style="font-weight:600;font-size:13px">${escHtml(u.display_name)}</div>
          <div style="font-size:11px;color:var(--text-muted)">@${escHtml(u.username)}</div></div>
        </div>`;
      });
    }
    if (channels.length) {
      html += `<div class="search-category">Channels</div>`;
      channels.forEach(c => {
        html += `<div class="search-result-item" onclick="window.location='/channels/${c.slug}/'">
          <div class="search-result-avatar" style="background:${c.color};border-radius:8px;font-size:16px">${escHtml(c.icon)}</div>
          <div style="font-weight:600;font-size:13px">#${escHtml(c.name)}</div>
        </div>`;
      });
    }
    if (discussions.length) {
      html += `<div class="search-category">Threads</div>`;
      discussions.forEach(d => {
        html += `<div class="search-result-item">
          <div class="search-result-avatar" style="background:var(--bg-input);font-size:16px">💬</div>
          <div style="font-size:13px;font-weight:500">${escHtml(d.title)}</div>
        </div>`;
      });
    }
    searchDropdown.innerHTML = html;
  }
  searchDropdown.classList.add("active");
}

const debouncedSearch = debounce(async q => {
  if (q.length < 2) { searchDropdown.classList.remove("active"); return; }
  try {
    const data = await apiFetch(`/discussions/search/?q=${encodeURIComponent(q)}`);
    renderSearchResults(data);
  } catch {}
}, 350);

globalSearch?.addEventListener("input",  e => debouncedSearch(e.target.value.trim()));
globalSearch?.addEventListener("focus",  () => { if (globalSearch.value.length >= 2) searchDropdown?.classList.add("active"); });
globalSearch?.addEventListener("keydown",e => { if (e.key === "Escape") { searchDropdown?.classList.remove("active"); globalSearch.blur(); }});
document.addEventListener("click", e => { if (!e.target.closest("#searchWrapper")) searchDropdown?.classList.remove("active"); });

/* ═══════════════════════════════════════════════════════════════════
   8. FRIEND PRESENCE POLLING
═══════════════════════════════════════════════════════════════════ */
async function pollFriendStatuses() {
  try {
    const data = await apiFetch("/accounts/api/friends/status/");
    if (!data.friends) return;
    const order = { active:0, away:1, offline:2 };
    let online = 0;
    data.friends.forEach(f => {
      if (f.status !== "offline") online++;
      document.querySelectorAll(`.friend-card[data-user-id="${f.id}"]`).forEach(card => {
        const ring = card.querySelector(".friend-status-ring");
        if (ring) ring.className = `friend-status-ring friend-status-ring--${f.status}`;
        const txt = card.querySelector(".friend-status-text");
        if (txt) txt.textContent = f.status;
        card.dataset.status = f.status;
      });
    });
    const badge = document.getElementById("friendCountBadge");
    if (badge) { badge.textContent = online || ""; badge.style.display = online ? "inline-flex" : "none"; }
  } catch {}
}

if (document.getElementById("friendsList")) {
  pollFriendStatuses();
  setInterval(pollFriendStatuses, 30_000);
}

/* ═══════════════════════════════════════════════════════════════════
   9. FRIEND PROFILE MODAL  (never auto-opens — only on explicit click)
═══════════════════════════════════════════════════════════════════ */
const friendModalOverlay = document.getElementById("friendModalOverlay");

function openFriendModal(cardEl) {
  if (!friendModalOverlay) return;
  const userId      = cardEl.dataset.userId;
  const displayName = cardEl.dataset.display;
  const color       = cardEl.dataset.color;
  const initial     = cardEl.dataset.initial;
  const avatarUrl   = cardEl.dataset.avatar;
  const status      = cardEl.dataset.status;
  const username    = cardEl.dataset.username;

  const statusColors = { active:"var(--green)", away:"var(--yellow)", offline:"var(--text-muted)" };

  document.getElementById("fmBanner").style.background =
    `linear-gradient(135deg,${color},color-mix(in srgb,${color} 60%,#1a1d26))`;

  const wrap = document.getElementById("fmAvatarWrap");
  wrap.innerHTML = avatarUrl
    ? `<img src="${escHtml(avatarUrl)}" alt="${escHtml(username)}" style="width:100%;height:100%;object-fit:cover;border-radius:50%" />`
    : `<div class="fm-avatar-initial" style="background:${color}">${escHtml(initial)}</div>`;
  wrap.style.boxShadow = `0 0 0 3px ${statusColors[status]||"var(--text-muted)"}`;

  document.getElementById("fmDisplayName").textContent = displayName;
  document.getElementById("fmUsername").textContent    = `@${username}`;
  document.getElementById("fmBio").textContent         = "Loading…";
  document.getElementById("fmStats").innerHTML         = "";

  apiFetch(`/accounts/api/profile-mini/${userId}/`)
    .then(d => {
      document.getElementById("fmBio").textContent = d.bio || "No bio yet.";
      document.getElementById("fmStats").innerHTML = `
        <div class="fm-stat"><span class="fm-stat-val">${d.friend_count??0}</span><span class="fm-stat-lbl">Friends</span></div>
        <div class="fm-stat"><span class="fm-stat-val">${d.thread_count??0}</span><span class="fm-stat-lbl">Threads</span></div>
        <div class="fm-stat"><span class="fm-stat-val">${d.channel_count??0}</span><span class="fm-stat-lbl">Channels</span></div>`;
    })
    .catch(() => { document.getElementById("fmBio").textContent = "Could not load profile."; });

  document.getElementById("fmChatBtn").onclick = () => {
    showToast(`DM with ${displayName} — coming soon!`, "info"); closeFriendModal();
  };
  document.getElementById("fmProfileLink").href = `/accounts/profile/${username}/`;

  friendModalOverlay.style.display = "flex";
}

function closeFriendModal(event) {
  if (event && event.target !== friendModalOverlay) return;
  if (friendModalOverlay) friendModalOverlay.style.display = "none";
}

/* ═══════════════════════════════════════════════════════════════════
  10. FRIEND REQUEST ACCEPT / REJECT
═══════════════════════════════════════════════════════════════════ */
async function respondFriendRequest(friendshipId, action, btn) {
  setButtonLoading(btn, true);
  try {
    await apiFetch(`/accounts/friend/respond/${friendshipId}/`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });

    // Remove from notification dropdown
    document.getElementById(`freq-${friendshipId}`)?.remove();
    // Remove from sidebar panel
    document.getElementById(`sfreq-${friendshipId}`)?.remove();

    // Update badge count
    const badge = document.getElementById("notifBadge");
    const countEl = document.getElementById("notifCount");
    let count = parseInt(badge?.textContent || "0", 10) - 1;
    count = Math.max(0, count);
    if (badge)   { badge.textContent = count || ""; badge.style.display = count ? "inline-flex" : "none"; }
    if (countEl) countEl.textContent = count;

    // Show empty state if no more requests
    const list = document.getElementById("notifList");
    if (list && list.querySelectorAll(".notif-item").length === 0) {
      document.getElementById("notifEmpty")?.remove();
      list.innerHTML = `<div class="notif-empty" id="notifEmpty">No pending requests</div>`;
    }

    showToast(action === "accept" ? "Friend request accepted! 🎉" : "Request declined.", action === "accept" ? "success" : "info");

    if (action === "accept") {
      // Reload page after short delay so new friend appears in sidebar
      setTimeout(() => window.location.reload(), 800);
    }
  } catch (e) {
    showToast(e.message, "error");
    setButtonLoading(btn, false);
  }
}

/* ═══════════════════════════════════════════════════════════════════
  11. CHANNEL DISCUSSIONS LOADER
═══════════════════════════════════════════════════════════════════ */
let _discSkip = 0;
const DISC_LIMIT = 20;

async function loadDiscussions(channelSlug, append = false) {
  const list = document.getElementById("discussionsList");
  if (!list) return;

  if (!append) {
    _discSkip = 0;
    list.innerHTML = `<div class="loading-spinner" id="discussionsLoader"><div class="spinner"></div></div>`;
  }

  try {
    const data = await apiFetch(`/discussions/${channelSlug}/?skip=${_discSkip}&limit=${DISC_LIMIT}`);
    document.getElementById("discussionsLoader")?.remove();

    if (!data.discussions?.length && !append) {
      list.innerHTML = renderEmptyDiscussions();
      document.getElementById("loadMoreWrap")?.style.setProperty("display","none");
      return;
    }

    data.discussions.forEach((d, i) => {
      const card = document.createElement("article");
      card.className = "disc-card";
      card.dataset.discId = d.id;
      card.style.setProperty("--accent", typeof CHANNEL_COLOR !== "undefined" ? CHANNEL_COLOR : "#5865F2");
      card.style.animationDelay = `${i * 35}ms`;
      card.innerHTML = renderDiscussionCard(d, channelSlug);
      list.appendChild(card);
    });

    _discSkip += data.discussions.length;
    const lmw = document.getElementById("loadMoreWrap");
    if (lmw) lmw.style.display = data.has_more ? "flex" : "none";
  } catch (e) {
    document.getElementById("discussionsLoader")?.remove();
    list.innerHTML = `<div class="empty-feed"><p>Failed to load threads: ${escHtml(e.message)}</p></div>`;
  }
}

function renderDiscussionCard(d, channelSlug) {
  const time  = new Date(d.created_at).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});
  const color = d.author_color || "#5865F2";
  const init  = (d.author_display || d.author_username || "?")[0].toUpperCase();
  const avatarHtml = d.author_avatar_url
    ? `<img src="${escHtml(d.author_avatar_url)}" style="width:22px;height:22px;border-radius:50%;object-fit:cover">`
    : `<div class="search-result-avatar" style="background:${color};width:22px;height:22px;font-size:10px">${escHtml(init)}</div>`;

  const modBtn = (typeof IS_MODERATOR !== "undefined" && IS_MODERATOR)
    ? `<button class="btn-ghost-custom btn-danger-ghost btn-xs-custom ms-auto"
               onclick="modDeleteDiscussion('${escHtml(channelSlug)}','${d.id}')">
         <i class="bi bi-shield-x"></i> Remove
       </button>`
    : `<a href="/discussions/${escHtml(channelSlug)}/${d.id}/" class="disc-read-more ms-auto">
         Read <i class="bi bi-arrow-right-short"></i>
       </a>`;

  return `
    <div class="disc-vote-col">
      <button class="upvote-btn" onclick="upvoteDiscussion('${d.id}',this)" title="Upvote">
        <i class="bi bi-arrow-up-circle-fill"></i>
      </button>
      <span class="vote-count">${d.upvotes}</span>
    </div>
    <div class="disc-content">
      <div class="disc-meta">
        <div style="display:flex;align-items:center;gap:6px">
          ${avatarHtml}
          <span style="font-size:12px;font-weight:600">${escHtml(d.author_display||d.author_username||"Unknown")}</span>
        </div>
        <span class="disc-time">${time}</span>
      </div>
      <a href="/discussions/${escHtml(channelSlug)}/${d.id}/" class="disc-title-link">
        <h2 class="disc-title">${escHtml(d.title)}</h2>
      </a>
      <p class="disc-excerpt">${escHtml(d.body)}</p>
      <div class="disc-footer">
        <span class="disc-stat"><i class="bi bi-chat-left-dots"></i> ${d.reply_count} replies</span>
        <span class="disc-stat"><i class="bi bi-arrow-up"></i> ${d.upvotes}</span>
        ${modBtn}
      </div>
    </div>`;
}

function renderEmptyDiscussions() {
  const canPost = typeof CAN_POST !== "undefined" && CAN_POST;
  return `<div class="empty-feed">
    <i class="bi bi-journals" style="font-size:3rem;opacity:.3"></i>
    <p>No threads yet.<br>${canPost ? "<strong>Be the first to start a discussion!</strong>" : "Join to participate."}</p>
  </div>`;
}

document.getElementById("loadMoreBtn")?.addEventListener("click", () => {
  if (typeof CHANNEL_SLUG !== "undefined") loadDiscussions(CHANNEL_SLUG, true);
});

/* ═══════════════════════════════════════════════════════════════════
  12. NEW DISCUSSION COMPOSER
═══════════════════════════════════════════════════════════════════ */
function openNewDiscussionModal() {
  const o = document.getElementById("newDiscussionOverlay");
  if (o) { o.style.display = "flex"; document.getElementById("newDiscTitle")?.focus(); }
}
function closeNewDiscussionModal(event) {
  if (event && event.target !== document.getElementById("newDiscussionOverlay")) return;
  const o = document.getElementById("newDiscussionOverlay");
  if (o) o.style.display = "none";
}
async function submitNewDiscussion(channelSlug) {
  const titleEl = document.getElementById("newDiscTitle");
  const bodyEl  = document.getElementById("newDiscBody");
  const title   = titleEl?.value.trim();
  const body    = bodyEl?.value.trim();
  if (!title) { showToast("Please enter a title.", "error"); titleEl?.focus(); return; }
  if (!body)  { showToast("Please write something.", "error"); bodyEl?.focus(); return; }
  const btn = document.querySelector("#newDiscussionModal .btn-primary-custom");
  setButtonLoading(btn, true);
  try {
    const data = await apiFetch(`/discussions/${channelSlug}/create/`, {
      method:"POST", body:JSON.stringify({title, body}),
    });
    showToast("Thread posted! 🎉","success");
    closeNewDiscussionModal();
    window.location.href = `/discussions/${channelSlug}/${data.discussion_id}/`;
  } catch(e) {
    showToast(e.message,"error");
  } finally {
    setButtonLoading(btn, false);
  }
}

/* ═══════════════════════════════════════════════════════════════════
  13. MESSAGE REPLY COMPOSER
═══════════════════════════════════════════════════════════════════ */
let _replyTargetId = null;

function setReplyTarget(messageId, authorName) {
  _replyTargetId = messageId;
  const banner = document.getElementById("replyTargetBanner");
  const text   = document.getElementById("replyTargetText");
  if (banner && text) {
    text.innerHTML = `<i class="bi bi-reply-fill"></i> Replying to <strong>${escHtml(authorName)}</strong>`;
    banner.style.display = "flex";
  }
  document.getElementById("messageInput")?.focus();
}
function clearReplyTarget() {
  _replyTargetId = null;
  const b = document.getElementById("replyTargetBanner");
  if (b) b.style.display = "none";
}

async function submitMessage(channelSlug, discussionId) {
  const input = document.getElementById("messageInput");
  const text  = input?.value.trim();
  if (!text) { showToast("Message cannot be empty.", "error"); return; }
  const btn = document.getElementById("sendMsgBtn");
  setButtonLoading(btn, true);
  try {
    const data = await apiFetch(`/discussions/${channelSlug}/${discussionId}/reply/`, {
      method:"POST", body:JSON.stringify({body:text, parent_message_id:_replyTargetId}),
    });
    input.value = "";
    document.getElementById("charCount").textContent = "0 / 2000";
    clearReplyTarget();
    appendMessageToThread(data);
    document.getElementById("noMsgPlaceholder")?.remove();
    showToast("Reply posted!","success");
  } catch(e) {
    showToast(e.message,"error");
  } finally {
    setButtonLoading(btn, false);
  }
}

function appendMessageToThread(msg) {
  const thread = document.getElementById("messagesThread");
  if (!thread) return;
  const card = document.createElement("div");
  card.id          = `msg-${msg.id}`;
  card.className   = "msg-card";
  card.dataset.msgId = msg.id;

  const avatarHtml = msg.author_avatar
    ? `<img src="${escHtml(msg.author_avatar)}" alt="${escHtml(msg.author_username)}" />`
    : `<div class="avatar-initial-sm" style="background:${msg.author_color}">${escHtml(msg.author_initial)}</div>`;

  const replyTag = msg.parent_message_id
    ? `<span class="msg-reply-tag"><i class="bi bi-reply-fill"></i> Reply</span>` : "";

  card.innerHTML = `
    <div class="msg-avatar">${avatarHtml}</div>
    <div class="msg-body-wrap">
      <div class="msg-header">
        <span class="msg-author">${escHtml(msg.author_display)}</span>
        <span class="msg-time">Just now</span>${replyTag}
        <div class="msg-actions ms-auto">
          <button class="msg-action-btn" title="Reply"
                  onclick="setReplyTarget('${msg.id}','${escHtml(msg.author_display)}')">
            <i class="bi bi-reply-fill"></i>
          </button>
        </div>
      </div>
      <div class="msg-content" id="msg-content-${msg.id}"></div>
    </div>`;
  card.querySelector(`#msg-content-${msg.id}`).textContent = msg.body;
  thread.appendChild(card);
  thread.scrollTo({top: thread.scrollHeight, behavior:"smooth"});
}

/* ═══════════════════════════════════════════════════════════════════
  14. UPVOTE  (fixed URL — /discussions/upvote/<id>/)
═══════════════════════════════════════════════════════════════════ */
async function upvoteDiscussion(discussionId, buttonEl) {
  if (buttonEl.classList.contains("voted")) return;
  try {
    await apiFetch(`/discussions/upvote/${discussionId}/`, {method:"POST"});
    buttonEl.classList.add("voted");
    const countEl = buttonEl.closest(".disc-vote-col,.disc-op-footer")
      ?.querySelector(".vote-count,.upvote-btn-inline span");
    if (countEl) countEl.textContent = parseInt(countEl.textContent,10) + 1;
    buttonEl.style.transform = "scale(1.3)";
    setTimeout(() => buttonEl.style.transform = "", 300);
  } catch(e) { showToast(e.message,"error"); }
}

/* ═══════════════════════════════════════════════════════════════════
  15. MODERATOR ACTIONS
═══════════════════════════════════════════════════════════════════ */
async function modDeleteMessage(channelSlug, messageId) {
  if (!confirm("Remove this message? The action is logged.")) return;
  try {
    const data = await apiFetch(`/discussions/mod/${channelSlug}/message/${messageId}/delete/`, {
      method:"POST", body:JSON.stringify({reason:""}),
    });
    const contentEl = document.getElementById(`msg-content-${messageId}`);
    if (contentEl) contentEl.innerHTML = `<em class="deleted-msg-text">${escHtml(data.placeholder)}</em>`;
    document.getElementById(`msg-${messageId}`)?.classList.add("msg-card--deleted");
    document.getElementById(`msg-${messageId}`)?.querySelectorAll(".msg-actions").forEach(a=>a.remove());
    showToast("Message removed.","success");
  } catch(e) { showToast(e.message,"error"); }
}

async function modDeleteDiscussion(channelSlug, discussionId) {
  if (!confirm("Remove this entire thread?")) return;
  try {
    await apiFetch(`/channels/${channelSlug}/mod/delete-discussion/`, {
      method:"POST", body:JSON.stringify({discussion_id:discussionId}),
    });
    const card = document.querySelector(`[data-disc-id="${discussionId}"]`);
    if (card) {
      card.style.transition = "opacity .35s,transform .35s";
      card.style.opacity    = "0";
      card.style.transform  = "translateX(40px)";
      setTimeout(() => card.remove(), 370);
    }
    showToast("Thread removed.","success");
  } catch(e) { showToast(e.message,"error"); }
}

/* ═══════════════════════════════════════════════════════════════════
  16. ACCESS REQUEST
═══════════════════════════════════════════════════════════════════ */
function openRequestModal()  { const o=document.getElementById("requestAccessOverlay"); if(o) o.style.display="flex"; }
function closeRequestModal(e){ if(e&&e.target!==document.getElementById("requestAccessOverlay")) return; const o=document.getElementById("requestAccessOverlay"); if(o) o.style.display="none"; }

async function submitAccessRequest(channelSlug) {
  const msg = document.getElementById("requestMsg")?.value.trim()||"";
  const btn = document.querySelector("#requestAccessModal .btn-primary-custom");
  setButtonLoading(btn,true);
  try {
    await apiFetch(`/channels/${channelSlug}/request-access/`,{method:"POST",body:JSON.stringify({message:msg})});
    showToast("Request sent! 🎉","success");
    closeRequestModal();
    const rb = document.getElementById("requestAccessBtn");
    if (rb) { rb.disabled=true; rb.textContent="Request Pending"; }
  } catch(e){ showToast(e.message||"Failed.","error"); } finally { setButtonLoading(btn,false); }
}

async function reviewAccessRequest(requestId, action, channelSlug) {
  const card = document.getElementById(`ar-${requestId}`);
  try {
    const data = await apiFetch(`/channels/access-request/${requestId}/review/`,{
      method:"POST", body:JSON.stringify({action}),
    });
    showToast(`Request ${data.status}.`,"success");
    if(card){ card.style.opacity="0"; card.style.transition="opacity .3s"; setTimeout(()=>card.remove(),320); }
    // Update member count badge if server returned new count
    if (data.member_count !== undefined) {
      document.querySelectorAll(".channel-member-count").forEach(el => {
        el.textContent = `${data.member_count} members`;
      });
    }
  } catch(e){ showToast(e.message,"error"); }
}

/* ═══════════════════════════════════════════════════════════════════
  17. INVITE FRIEND
═══════════════════════════════════════════════════════════════════ */
function openInviteModal() {
  const overlay = document.getElementById("inviteModalOverlay");
  const listEl  = document.getElementById("inviteFriendsList");
  if (!overlay||!listEl) return;
  overlay.style.display = "flex";
  listEl.innerHTML = `<div class="loading-spinner"><div class="spinner"></div></div>`;
  apiFetch("/accounts/api/friends/status/").then(data => {
    const friends = data.friends||[];
    if (!friends.length) { listEl.innerHTML=`<div class="empty-feed" style="padding:24px"><p>No friends yet.</p></div>`; return; }
    listEl.innerHTML = friends.map(f => {
      const av = f.avatar_url
        ? `<img src="${escHtml(f.avatar_url)}" class="friend-avatar" />`
        : `<div class="friend-avatar friend-avatar--initial" style="background:${f.avatar_color}">${escHtml(f.initial)}</div>`;
      return `<div class="friend-card" style="cursor:default">
        <div class="friend-avatar-wrap">${av}<span class="friend-status-ring friend-status-ring--${f.status}"></span></div>
        <div class="friend-info"><span class="friend-name">${escHtml(f.display_name)}</span><span class="friend-status-text">${f.status}</span></div>
        <button class="btn-secondary-custom btn-sm-custom" style="margin-left:auto"
                onclick="sendInvite('${typeof CHANNEL_SLUG!=='undefined'?CHANNEL_SLUG:''}',${f.id},'${escHtml(f.display_name)}',this)">
          <i class="bi bi-send-fill"></i> Invite
        </button>
      </div>`;
    }).join("");
  }).catch(()=>{ listEl.innerHTML=`<div class="empty-feed" style="padding:24px"><p>Could not load friends.</p></div>`; });
}
function closeInviteModal(e){ if(e&&e.target!==document.getElementById("inviteModalOverlay")) return; const o=document.getElementById("inviteModalOverlay"); if(o) o.style.display="none"; }
async function sendInvite(channelSlug,userId,displayName,btn) {
  setButtonLoading(btn,true);
  try {
    await apiFetch(`/channels/${channelSlug}/invite/`,{method:"POST",body:JSON.stringify({user_id:userId})});
    btn.innerHTML=`<i class="bi bi-check-lg"></i> Invited`; btn.disabled=true;
    showToast(`Invited ${displayName}!`,"success");
  } catch(e){ showToast(e.message,"error"); setButtonLoading(btn,false); }
}

/* ═══════════════════════════════════════════════════════════════════
  18. PAGE INIT
═══════════════════════════════════════════════════════════════════ */
document.addEventListener("DOMContentLoaded", () => {
  // Highlight active channel in sidebar
  const path = window.location.pathname;
  document.querySelectorAll(".channel-nav-item").forEach(item => {
    if (item.dataset.channelSlug && path.includes(`/channels/${item.dataset.channelSlug}/`)) {
      item.classList.add("active");
    }
  });

  // Message input char counter
  const msgInput = document.getElementById("messageInput");
  if (msgInput) {
    msgInput.addEventListener("input",()=>{
      document.getElementById("charCount").textContent = `${msgInput.value.length} / 2000`;
    });
    msgInput.addEventListener("keydown",e=>{
      if ((e.ctrlKey||e.metaKey) && e.key==="Enter") submitMessage(
        typeof CHANNEL_SLUG!=="undefined"?CHANNEL_SLUG:"",
        typeof DISCUSSION_ID!=="undefined"?DISCUSSION_ID:""
      );
    });
  }

  // Scroll messages thread to bottom
  const thread = document.getElementById("messagesThread");
  if (thread) thread.scrollTop = thread.scrollHeight;

  // Page fade-in
  const main = document.getElementById("mainContent");
  if (main) {
    main.style.opacity = "0"; main.style.transform = "translateY(6px)";
    main.style.transition = "opacity .3s ease,transform .3s ease";
    requestAnimationFrame(()=>{ main.style.opacity="1"; main.style.transform="translateY(0)"; });
  }
});

// Expose globals for inline template onclick handlers
Object.assign(window, {
  openFriendModal, closeFriendModal,
  respondFriendRequest,
  upvoteDiscussion, modDeleteMessage, modDeleteDiscussion,
  submitNewDiscussion, openNewDiscussionModal, closeNewDiscussionModal,
  submitMessage, setReplyTarget, clearReplyTarget,
  loadDiscussions, openRequestModal, closeRequestModal,
  submitAccessRequest, reviewAccessRequest,
  openInviteModal, closeInviteModal, sendInvite,
  apiFetch, showToast, setButtonLoading, escHtml,
});
