(() => {
  "use strict";

  const state = { serviceType:null, airportCode:null, passengerCount:null, luggageCount:null, childSeat:null, oversizedItems:null, contactMethod:null, estimateId:null };
  const form = document.getElementById("quoteForm");
  if (!form) return;
  const continueButton = document.getElementById("continueButton");
  const estimatePanel = document.getElementById("estimatePanel");
  const successPanel = document.getElementById("successPanel");
  const todayValue = dateInTimeZone("America/Los_Angeles");
  document.getElementById("serviceDate").min = todayValue;
  populateArrivalTimes();
  updateContactFields();

  form.querySelectorAll("[data-choice-group]").forEach((group) => group.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-value]");
    if (!button) return;
    const key = group.dataset.choiceGroup;
    state[key] = button.dataset.value;
    if (key !== "contactMethod") invalidateEstimate();
    group.querySelectorAll("button[data-value]").forEach((item) => {
      const selected = item === button;
      item.classList.toggle("is-selected", selected);
      item.setAttribute("aria-pressed", String(selected));
    });
    clearError(key);
    if (key === "serviceType") updateLabels();
    if (key === "contactMethod") updateContactFields();
  }));

  ["serviceDate", "flightNumber", "locationInput"].forEach((id) => document.getElementById(id).addEventListener("input", invalidateEstimate));
  document.getElementById("flight-arrival-time").addEventListener("change", invalidateEstimate);

  continueButton.addEventListener("click", async () => {
    if (!validateTrip()) return focusFirstError();
    clearError("estimateRequest");
    setLoading(true);
    try {
      const trip = collectTripData();
      const estimate = await requestEstimate(trip);
      state.estimateId = estimate.estimate_id;
      renderEstimate(estimate, trip);
      estimatePanel.hidden = false;
      estimatePanel.focus();
      estimatePanel.scrollIntoView({ behavior:"smooth", block:"start" });
    } catch (error) {
      setError("estimateRequest", error instanceof EstimateRequestError ? error.message : "Unable to get an estimate right now. Please try again.");
    } finally { setLoading(false); }
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.estimateId) { setError("estimateRequest", "Please get a current estimate first."); return; }
    if (!validateContact()) return focusFirstError();
    const submitButton = document.getElementById("submitRequestButton");
    submitButton.disabled = true;
    submitButton.textContent = "Submitting…";
    clearError("contact");
    try {
      const response = await fetch("/api/v1/quote-requests", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          estimate_id: state.estimateId,
          customer_name: value("customerName").trim(),
          phone: value("customerPhone").trim() || null,
          email: value("customerEmail").trim() || null,
          wechat_id: value("customerWechat").trim() || null,
          line_id: value("customerLine").trim() || null,
          preferred_contact_method: state.contactMethod || null,
          source: value("source") || null,
          estimate_acceptance: true
        })
      });
      let body = null;
      try { body = await response.json(); } catch (_) {}
      if (!response.ok) throw new EstimateRequestError(body?.error?.message || "Unable to submit your request. Please try again.");
      window.location.assign(`/quote/confirmation?reference=${encodeURIComponent(body.order_id)}`);
    } catch (error) {
      setError("contact", error instanceof EstimateRequestError ? error.message : "Unable to submit your request. Please try again.");
      submitButton.disabled = false;
      submitButton.textContent = "Send request to Jason — final fare to be confirmed";
    }
  });
  document.getElementById("startOverButton").addEventListener("click", resetForm);
  document.getElementById("requestConfirmationButton").addEventListener("click", () => {
    const contactDetails = document.getElementById("contactDetails");
    contactDetails.scrollIntoView({ behavior:"smooth", block:"start" });
    contactDetails.focus({ preventScroll:true });
  });
  form.querySelectorAll("[data-copy-contact]").forEach((button) => button.addEventListener("click", async () => {
    const label = button.dataset.copyLabel || "Contact information";
    const original = button.textContent;
    try {
      await navigator.clipboard.writeText(button.dataset.copyContact || "");
      button.textContent = `${label} copied`;
    } catch (_) {
      button.textContent = button.dataset.copyContact || original;
    }
  }));

  function validateTrip() {
    const checks = [
      requireChoice("serviceType", "Choose Airport Pickup or Airport Dropoff."),
      requireChoice("airportCode", "Choose an airport."), validateSchedule(), validateLocation(),
      requireChoice("passengerCount", "Choose passenger count."), requireChoice("luggageCount", "Choose luggage count."),
      requireChoice("childSeat", "Choose Yes or No."), requireChoice("oversizedItems", "Choose Yes or No.")
    ];
    return checks.every(Boolean);
  }
  function requireChoice(key, message) { if (state[key]) { clearError(key); return true; } setError(key, message); return false; }
  function validateSchedule() {
    const date = document.getElementById("serviceDate"), time = document.getElementById("flight-arrival-time");
    date.removeAttribute("aria-invalid"); time.removeAttribute("aria-invalid");
    if (!date.value || !time.value) { if (!date.value) date.setAttribute("aria-invalid","true"); if (!time.value) time.setAttribute("aria-invalid","true"); setError("schedule","Choose both a date and time."); return false; }
    if (date.value < todayValue) { date.setAttribute("aria-invalid","true"); setError("schedule","The service date cannot be in the past."); return false; }
    clearError("schedule"); return true;
  }
  function validateLocation() {
    const input = document.getElementById("locationInput"), value = input.value.trim();
    input.removeAttribute("aria-invalid");
    if (!value || (/^\d+$/.test(value) && !/^\d{5}$/.test(value))) { input.setAttribute("aria-invalid","true"); setError("locationInput", value ? "Enter a 5-digit ZIP Code or a City name." : "Enter a ZIP Code or City."); return false; }
    clearError("locationInput"); return true;
  }
  function validateContact() {
    const name=document.getElementById("customerName"), phone=document.getElementById("customerPhone"), email=document.getElementById("customerEmail"), wechat=document.getElementById("customerWechat"), line=document.getElementById("customerLine"), hasPhone=!!phone.value.trim(), hasEmail=!!email.value.trim(), hasWechat=!!wechat.value.trim(), hasLine=!!line.value.trim();
    phone.removeAttribute("aria-invalid"); email.removeAttribute("aria-invalid"); wechat.removeAttribute("aria-invalid"); line.removeAttribute("aria-invalid");
    name.removeAttribute("aria-invalid");
    if (!name.value.trim()) { name.setAttribute("aria-invalid","true"); setError("contact","Enter your name."); return false; }
    if (!hasPhone && !hasEmail && !hasWechat && !hasLine) { phone.setAttribute("aria-invalid","true"); email.setAttribute("aria-invalid","true"); wechat.setAttribute("aria-invalid","true"); line.setAttribute("aria-invalid","true"); setError("contact","Enter a phone number, email address, WeChat ID, or LINE ID."); return false; }
    if (state.contactMethod === "SMS" && !hasPhone) { phone.setAttribute("aria-invalid","true"); setError("contact","Enter a phone number for text contact."); return false; }
    if (state.contactMethod === "EMAIL" && !hasEmail) { email.setAttribute("aria-invalid","true"); setError("contact","Enter an email address for email contact."); return false; }
    if (state.contactMethod === "WECHAT" && !hasWechat) { wechat.setAttribute("aria-invalid","true"); setError("contact","Enter a WeChat ID."); return false; }
    if (state.contactMethod === "LINE" && !hasLine) { line.setAttribute("aria-invalid","true"); setError("contact","Enter a LINE ID or other contact information."); return false; }
    if (hasEmail && !email.checkValidity()) { email.setAttribute("aria-invalid","true"); setError("contact","Enter a valid email address."); return false; }
    clearError("contact"); return true;
  }

  function updateContactFields() {
    const method = state.contactMethod;
    document.getElementById("phoneField").hidden = !!method && method !== "SMS";
    document.getElementById("emailField").hidden = !!method && method !== "EMAIL";
    document.getElementById("wechatField").hidden = method !== "WECHAT";
    document.getElementById("lineField").hidden = method !== "LINE";
  }

  function collectTripData() { return { serviceType:state.serviceType, airportCode:state.airportCode, date:value("serviceDate"), time:value("flight-arrival-time"), flightNumber:value("flightNumber").trim(), location:value("locationInput").trim(), passengers:state.passengerCount, luggage:state.luggageCount, childSeat:state.childSeat, oversizedItems:state.oversizedItems }; }
  async function requestEstimate(trip) {
    const payload = { service_type:trip.serviceType, airport_code:trip.airportCode, service_date:trip.date, service_time:trip.time, service_timezone:"America/Los_Angeles", flight_number:trip.flightNumber || null, location_input:trip.location, passenger_count:trip.passengers, large_luggage_count:trip.luggage, child_seat_required:trip.childSeat === "YES", oversized_items:trip.oversizedItems === "YES" };
    let response;
    try { response = await fetch("/api/v1/quote-estimates", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload) }); }
    catch (_) { throw new EstimateRequestError("Unable to connect. Check your connection and try again."); }
    let body; try { body = await response.json(); } catch (_) { throw new EstimateRequestError("The estimate service returned an invalid response."); }
    if (!response.ok) {
      if (response.status === 422) throw new EstimateRequestError(Array.isArray(body?.detail) ? body.detail[0]?.msg : "Please review the trip details.");
      if (response.status === 400) throw new EstimateRequestError(body?.error?.message || "Jason cannot estimate this trip yet.");
      throw new EstimateRequestError("The estimate service is temporarily unavailable. Please try again.");
    }
    return body;
  }
  function renderEstimate(estimate, trip) {
    const manual = estimate.status === "MANUAL_REVIEW_REQUIRED";
    const hasRange = estimate.estimated_min_amount != null && estimate.estimated_max_amount != null;
    const range = document.getElementById("estimateRange"); range.textContent = hasRange ? `${formatUsd(estimate.estimated_min_amount)} - ${formatUsd(estimate.estimated_max_amount)}` : ""; range.hidden = !hasRange;
    document.getElementById("manualReview").hidden = !manual;
    document.getElementById("estimateRoute").textContent = estimate.route_summary;
    const summary = [["Passengers",trip.passengers],["Luggage",trip.luggage],["Child seat",trip.childSeat === "YES" ? "Requested" : "No"],["Vehicle",displayVehicle(estimate.vehicle_assessment)],["Date & time",`${trip.date} · ${formatTime(trip.time)}`]];
    document.getElementById("estimateSummary").innerHTML = summary.map(([k,v])=>`<div><dt>${escapeHtml(k)}</dt><dd>${escapeHtml(v)}</dd></div>`).join("");
    const notices = ["This is a preliminary planning range. Jason will review the exact route, pickup time, luggage, and availability before confirming the final fare."]; if (trip.childSeat === "YES") notices.push("Child seat availability will be confirmed with your trip.");
    document.getElementById("estimateNotices").innerHTML = notices.map((x)=>`<p>${escapeHtml(x)}</p>`).join("");
    document.getElementById("estimateValidity").textContent = formatValidity(estimate.valid_until);
  }
  function invalidateEstimate() { state.estimateId=null; estimatePanel.hidden=true; }
  function populateArrivalTimes() {
    const select = document.getElementById("flight-arrival-time");
    for (let minutes = 0; minutes < 24 * 60; minutes += 30) {
      const hour = Math.floor(minutes / 60), minute = minutes % 60;
      const option = document.createElement("option");
      option.value = `${String(hour).padStart(2,"0")}:${String(minute).padStart(2,"0")}`;
      option.textContent = `${hour % 12 || 12}:${String(minute).padStart(2,"0")} ${hour < 12 ? "AM" : "PM"}`;
      select.appendChild(option);
    }
  }
  function setLoading(on) { continueButton.disabled=on; continueButton.textContent=on ? "Getting estimate…" : "Next: Get Estimate"; form.setAttribute("aria-busy",String(on)); }
  function updateLabels() { const drop=state.serviceType === "AIRPORT_DROPOFF"; document.getElementById("locationLabel").textContent=drop?"Pickup ZIP Code or City":"Destination ZIP Code or City"; document.getElementById("dateLabel").textContent=drop?"Pickup Date":"Flight Arrival Date"; document.getElementById("timeLabel").textContent=drop?"Pickup Time":"Flight Arrival Time"; document.getElementById("scheduleGuidance").textContent=drop?"When should Jason pick you up? Los Angeles time zone.":"Enter your scheduled flight arrival time. Los Angeles time zone."; }
  function focusFirstError(){ const target=form.querySelector('[aria-invalid="true"], .field-error:not(:empty)'); if(target){ target.focus?.(); target.scrollIntoView({behavior:"smooth",block:"center"}); } }
  function setError(key,msg){ const el=form.querySelector(`[data-error-for="${key}"]`); if(el) el.textContent=msg; if(key === "estimateRequest") document.getElementById("estimateErrorContact").hidden = !msg; } function clearError(key){setError(key,"");} function value(id){return document.getElementById(id).value;}
  function formatUsd(v){return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(v));}
  function formatTime(v){const [h,m]=v.split(":"),n=Number(h);return `${n%12||12}:${m} ${n>=12?"PM":"AM"}`;}
  function displayVehicle(v){return ({LIKELY_COMFORTABLE:"Likely comfortable",NEEDS_CONFIRMATION:"Needs confirmation",NOT_RECOMMENDED:"Not recommended",INSUFFICIENT_INFORMATION:"Needs more information"})[v]||"Jason review required";}
  function formatValidity(v){const t=Date.parse(v);return Number.isFinite(t)?`Estimate valid until ${new Intl.DateTimeFormat("en-US",{timeZone:"America/Los_Angeles",month:"short",day:"numeric",hour:"numeric",minute:"2-digit",timeZoneName:"short"}).format(t)}. Final price requires Jason confirmation.`:"Final price requires Jason confirmation.";}
  function dateInTimeZone(zone){const p=new Intl.DateTimeFormat("en-US",{timeZone:zone,year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(Date.now()),o=Object.fromEntries(p.map(x=>[x.type,x.value]));return `${o.year}-${o.month}-${o.day}`;}
  function escapeHtml(v){const e=document.createElement("span");e.textContent=String(v);return e.innerHTML;}
  function resetForm(){form.reset();Object.keys(state).forEach((k)=>state[k]=null);form.querySelectorAll(".is-selected").forEach((x)=>x.classList.remove("is-selected"));form.querySelectorAll("[aria-pressed]").forEach((x)=>x.setAttribute("aria-pressed","false"));form.querySelectorAll(".field-error").forEach((x)=>x.textContent="");form.hidden=false;estimatePanel.hidden=true;successPanel.hidden=true;updateContactFields();window.scrollTo({top:form.offsetTop,behavior:"smooth"});}
  class EstimateRequestError extends Error {}
})();
