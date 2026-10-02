(() => {
  const laterKey = "pwa-install-later";
  const banner = document.getElementById("pwa-install");
  const installBtn = document.getElementById("pwa-install-btn");
  const laterBtn = document.getElementById("pwa-later-btn");
  const iosHint = document.getElementById("pwa-ios-hint");
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent || "");
  let deferred;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event;
    if (banner && !localStorage.getItem(laterKey)) {
      banner.hidden = false;
      banner.classList.remove("d-none");
    }
  });
  if (banner && isIOS && !localStorage.getItem(laterKey) && !window.navigator.standalone) {
    banner.hidden = false;
    banner.classList.remove("d-none");
    iosHint?.classList.remove("d-none");
    if (installBtn) installBtn.hidden = true;
  }
  installBtn?.addEventListener("click", async () => {
    if (!deferred) return;
    deferred.prompt();
    await deferred.userChoice;
    deferred = null;
    if (banner) banner.hidden = true;
  });
  laterBtn?.addEventListener("click", () => {
    localStorage.setItem(laterKey, "1");
    if (banner) banner.hidden = true;
  });
})();

(() => {
  const ua = navigator.userAgent || "";
  const isInApp = /KAKAOTALK|NAVER|Instagram|FBAN|FBAV/i.test(ua);
  if (!isInApp) return;

  const el = document.getElementById("inapp-escape");
  if (!el) return;
  el.classList.remove("d-none");
  const url = location.href;
  const isAndroid = /Android/i.test(ua);
  if (isAndroid) {
    const intent = `intent://${location.host}${location.pathname}${location.search}#Intent;scheme=https;package=com.android.chrome;end`;
    el.innerHTML = `인앱 브라우저입니다. <a href="${intent}">Chrome에서 열기</a>`;
  } else {
    el.innerHTML = `Safari에서 열어주세요. <button type="button" id="copy-link" class="btn btn-sm btn-outline-secondary">링크 복사</button>`;
    document.getElementById("copy-link")?.addEventListener("click", async () => {
      await navigator.clipboard.writeText(url);
    });
  }
})();
