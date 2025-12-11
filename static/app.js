document.addEventListener("DOMContentLoaded", function () {
  const rxLed = document.getElementById("rx-led");
  const txLed = document.getElementById("tx-led");
  const output = document.getElementById("terminal-scroll-content");
  const terminalForm = document.getElementById("terminal-form");
  const terminalInput = document.getElementById("terminal-input");
  const copyBtn = document.getElementById("copy-output");
  const downloadBtn = document.getElementById("download-output");
  const clearBtn = document.getElementById("clear-output");

  const ws = new WebSocket(`ws://${location.host}/ws`);

  let expectPassword = false;

  function getTerminalText() {
    return output.innerText || output.textContent || "";
  }

  clearBtn.addEventListener("click", () => {
    output.innerHTML = "";
    output.scrollTop = 0;
  });

  function flash(btn, text, millis = 1000) {
    const old = btn.textContent;
    btn.textContent = text;
    setTimeout(() => (btn.textContent = old), millis);
  }

  copyBtn.addEventListener("click", async () => {
    const text = getTerminalText();
    if (!text) return flash(copyBtn, "Nothing to copy");
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      flash(copyBtn, "Copied!");
    } catch {
      flash(copyBtn, "Copy failed");
    }
  });

  function dateStamp() {
    const d = new Date();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const yyyy = d.getFullYear();
    return `${mm}_${dd}_${yyyy}`;
  }

  downloadBtn.addEventListener("click", () => {
    const text = getTerminalText();
    if (!text) return flash(downloadBtn, "Nothing to download");

    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pb_output_${dateStamp()}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  function setInputForPassword(on) {
    if (on) {
      terminalInput.type = "password";
      terminalInput.placeholder = "Password";
      terminalInput.autocomplete = "current-password";
    } else {
      terminalInput.type = "text";
      terminalInput.placeholder = "Enter command...";
      terminalInput.autocomplete = "off";
    }
  }

  ws.onmessage = function (event) {
    try {
      const data = JSON.parse(event.data);

      if (data.rx) {
        rxLed.classList.add("on");
        setTimeout(() => rxLed.classList.remove("on"), 100);
      }
      if (data.tx) {
        txLed.classList.add("on");
        setTimeout(() => txLed.classList.remove("on"), 100);
      }

      if (data.output) {
        const div = document.createElement("div");
        div.textContent = data.output;
        output.appendChild(div);
        output.scrollTop = output.scrollHeight;

        const out = data.output;
        if (/\bpassword\s*:?\s*$/i.test(out) || out.toLowerCase().includes("password:")) {
          expectPassword = true;
          setInputForPassword(true);
        } else if (
          /\b(username|user\s*name|login)\s*:?\s*$/i.test(out) ||
          out.trim().endsWith(">") ||
          out.trim().endsWith("#")
        ) {
          expectPassword = false;
          setInputForPassword(false);
        }
      }

      if (data.rx_bps !== undefined && data.tx_bps !== undefined) {
        document.getElementById("rx-rate").textContent = `${data.rx_bps} B/s`;
        document.getElementById("tx-rate").textContent = `${data.tx_bps} B/s`;
      }

      if (data.mem_alloc !== undefined && data.mem_free !== undefined) {
        document.getElementById("mem-alloc").textContent =
          `${data.mem_alloc.toLocaleString()} B`;
        document.getElementById("mem-free").textContent =
          `${data.mem_free.toLocaleString()} B`;
      }
    } catch (err) {
      console.error("WebSocket error:", err);
    }
  };

  terminalForm.addEventListener("submit", e => {
    e.preventDefault();
    const val = terminalInput.value;
    ws.send(JSON.stringify({ input: val }));

    if (expectPassword) {
      expectPassword = false;
      setInputForPassword(false);
    }

    terminalInput.value = "";
  });

  function loadPBSettings() {
    fetch('/api/v1/pb/settings')
      .then(res => res.json())
      .then(settings => {
        document.getElementById("pb-plugged-device").textContent = settings.plugged_device;
        document.getElementById("pb-location").textContent = settings.location;

        document.getElementById("baudrate").textContent = settings.baudrate;
        document.getElementById("bits").textContent = settings.bits;
        document.getElementById("parity").textContent = settings.parity;
        document.getElementById("stop").textContent = settings.stop;
      })
      .catch(console.error);
  }

  loadPBSettings();

  // IDENTIFY BUTTON LOGIC
  const identifyBtn = document.getElementById("identify-btn");
  let identifyActive = false;

  async function refreshIdentifyState() {
    try {
      const res = await fetch("/api/v1/pb/identify");
      const data = await res.json();

      identifyActive = Boolean(data.identify);

      if (identifyActive) {
        identifyBtn.textContent = "Stop Identify";
        identifyBtn.classList.add("active");
      } else {
        identifyBtn.textContent = "Identify Device";
        identifyBtn.classList.remove("active");
      }
    } catch (e) {
      console.error("Failed to refresh identify state", e);
    }
  }

  identifyBtn.addEventListener("click", async () => {
    if (identifyActive) {
      await fetch("/api/v1/pb/identify/stop");
    } else {
      await fetch("/api/v1/pb/identify/start");
    }
    await refreshIdentifyState();
  });

  refreshIdentifyState();

  const modal = document.getElementById("settings-modal");
  const settingsForm = document.getElementById("settings-form");
  const closeBtn = document.getElementById("modal-close");

  const adhocFields = document.getElementById("adhoc-fields");
  const infraFields = document.getElementById("infra-fields");
  const adhocToggle = document.getElementById("is_ad_hoc");

  function updateWifiVisibility() {
    const on = adhocToggle.checked;
    adhocFields.style.display = on ? "" : "none";
    infraFields.style.display = on ? "none" : "";
  }

  adhocToggle.addEventListener("change", updateWifiVisibility);

  /* ------------------------------
     SCREENSAVER UI ELEMENTS
  ------------------------------ */
  const ssToggle = document.getElementById("screensaver_enabled");
  const ssTimerContainer = document.getElementById("screensaver-timer-container");
  const ssTimerSlider = document.getElementById("screensaver_idle_timer_s");
  const ssTimerValue = document.getElementById("screensaver-timer-value");

  function updateScreensaverVisibility() {
    const enabled = ssToggle.checked;
    ssTimerContainer.classList.toggle("hidden", !enabled);
  }

  ssTimerSlider?.addEventListener("input", () => {
    ssTimerValue.textContent = ssTimerSlider.value;
  });

  ssToggle?.addEventListener("change", updateScreensaverVisibility);

  /* ------------------------------ */

  document.getElementById("settings-btn").addEventListener("click", () => {
    fetch('/api/v1/pb/settings')
      .then(res => res.json())
      .then(settings => {
        console.log(settings);

        settingsForm.plugged_device.value = settings.plugged_device || '';
        settingsForm.location.value = settings.location || '';

        settingsForm.baudrate.value = settings.uart.baudrate;
        settingsForm.bits.value = settings.uart.bits;
        settingsForm.parity.value = settings.uart.parity ?? "None";
        settingsForm.stop.value = settings.uart.stop;

        const wlan = settings.wlan || {};
        const isAdHoc = Boolean(wlan.is_ad_hoc);
        const adhoc = wlan.ad_hoc || {};
        const infra = wlan.infrastructure || {};

        settingsForm.is_ad_hoc.checked = isAdHoc;

        settingsForm.ssid_adhoc.value = adhoc.ssid || 'PicoBridge';
        settingsForm.psk_adhoc.value = adhoc.psk || '';
        settingsForm.ssid_infra.value = infra.ssid || '';
        settingsForm.psk_infra.value = infra.psk || '';

        updateWifiVisibility();

        // Load screensaver settings
        const ss = settings.screensaver || {};
        settingsForm.screensaver_enabled.checked = ss.enabled ?? false;
        settingsForm.screensaver_idle_timer_s.value = ss.idle_timer_s ?? 60;
        ssTimerValue.textContent = settingsForm.screensaver_idle_timer_s.value;

        updateScreensaverVisibility();

        modal.classList.remove("hidden");
      });
  });

  closeBtn.addEventListener("click", () => modal.classList.add("hidden"));

  settingsForm.addEventListener("submit", e => {
    e.preventDefault();

    const isAdHoc = settingsForm.querySelector('[name="is_ad_hoc"]').checked;

    const wlan = {
      is_ad_hoc: isAdHoc,
      ad_hoc: {
        ssid: settingsForm.querySelector('[name="ssid_adhoc"]').value || 'PicoBridge',
        psk: settingsForm.querySelector('[name="psk_adhoc"]').value || ''
      },
      infrastructure: {
        ssid: settingsForm.querySelector('[name="ssid_infra"]').value || '',
        psk: settingsForm.querySelector('[name="psk_infra"]').value || ''
      }
    };

    const screensaver = {
      screensaver_enabled: settingsForm.querySelector('[name="screensaver_enabled"]').checked,
      screensaver_idle_timer_s: parseInt(settingsForm.querySelector('[name="screensaver_idle_timer_s"]').value) || 60
    };

    const data = {
      plugged_device: settingsForm.querySelector('[name="plugged_device"]').value,
      location: settingsForm.querySelector('[name="location"]').value,

      baudrate: parseInt(settingsForm.querySelector('[name="baudrate"]').value),
      bits: parseInt(settingsForm.querySelector('[name="bits"]').value),
      parity: settingsForm.querySelector('[name="parity"]').value === "None"
        ? null
        : parseInt(settingsForm.querySelector('[name="parity"]').value),
      stop: parseInt(settingsForm.querySelector('[name="stop"]').value),
      wlan,
      screensaver
    };

    fetch('/api/v1/pb/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    }).then(res => {
      if (res.ok) {
        modal.classList.add("hidden");
        loadPBSettings();
      } else {
        alert("Failed to update settings.");
      }
    }).catch(console.error);
  });

});
