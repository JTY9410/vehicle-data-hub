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
