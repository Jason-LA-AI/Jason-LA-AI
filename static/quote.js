(() => {
  "use strict";

  const TOTAL_STEPS = 7;
  const stepNames = ["Service", "Airport", "Schedule", "Location", "Trip details", "Estimate", "Contact"];
  const state = {
    serviceType: null,
    airportCode: null,
    passengerCount: null,
    luggageCount: null,
    childSeat: null,
    oversizedItems: null,
    contactMethod: null,
    estimateAccepted: false,
    estimateId: null,
  };

  const form = document.getElementById("quoteForm");
  if (!form) return;

  const steps = Array.from(form.querySelectorAll(".quote-step"));
  const continueButton = document.getElementById("continueButton");
  const backButton = document.getElementById("backButton");
  const stepActions = document.getElementById("stepActions");
  const progressBar = document.getElementById("progressBar");
  const progressLabel = document.getElementById("progressLabel");
  const progressName = document.getElementById("progressName");
  const successPanel = document.getElementById("successPanel");
  let currentStep = 1;

  const todayValue = dateInTimeZone("America/Los_Angeles");
  document.getElementById("serviceDate").min = todayValue;

  form.querySelectorAll("[data-choice-group]").forEach((group) => {
    group.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-value]");
      if (!button) return;

      const key = group.dataset.choiceGroup;
      state[key] = button.dataset.value;
      if (key !== "contactMethod") state.estimateId = null;
      group.querySelectorAll("button[data-value]").forEach((item) => {
        const selected = item === button;
        item.classList.toggle("is-selected", selected);
        item.setAttribute("aria-pressed", String(selected));
      });
      clearError(key);
      if (key === "serviceType") updateLocationLabel();
    });
  });

  continueButton.addEventListener("click", async () => {
    if (!validateStep(currentStep)) return;
    if (currentStep === 5) {
      await loadEstimate();
      return;
    }
    showStep(currentStep + 1);
  });

  backButton.addEventListener("click", () => showStep(currentStep - 1));

  document.getElementById("acceptEstimateButton").addEventListener("click", () => {
    state.estimateAccepted = true;
    showStep(7);
  });

  document.getElementById("editTripButton").addEventListener("click", () => {
    state.estimateAccepted = false;
    state.estimateId = null;
    showStep(1);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!validateContact()) return;
    form.hidden = true;
    document.querySelector(".quote-progress").hidden = true;
    successPanel.hidden = false;
    successPanel.focus();
  });

  document.getElementById("startOverButton").addEventListener("click", resetPrototype);

  function showStep(stepNumber) {
    if (stepNumber < 1 || stepNumber > TOTAL_STEPS) return;
    currentStep = stepNumber;
    steps.forEach((step) => {
      const active = Number(step.dataset.step) === currentStep;
      step.hidden = !active;
      step.classList.toggle("is-active", active);
    });

    progressBar.style.width = `${(currentStep / TOTAL_STEPS) * 100}%`;
    progressLabel.textContent = `Step ${currentStep} of ${TOTAL_STEPS}`;
    progressName.textContent = stepNames[currentStep - 1];
    backButton.hidden = currentStep === 1;
    continueButton.hidden = currentStep >= 6;
    stepActions.hidden = currentStep >= 6;

    const heading = steps[currentStep - 1].querySelector("h2");
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus();
    }
  }

  function validateStep(stepNumber) {
    if (stepNumber === 1) return requireChoice("serviceType", "Choose Airport Pickup or Airport Dropoff.");
    if (stepNumber === 2) return requireChoice("airportCode", "Choose an airport.");
    if (stepNumber === 3) return validateSchedule();
    if (stepNumber === 4) return validateLocation();
    if (stepNumber === 5) {
      const checks = [
        requireChoice("passengerCount", "Choose the passenger count."),
        requireChoice("luggageCount", "Choose the large luggage count."),
        requireChoice("childSeat", "Choose Yes or No for a child seat."),
        requireChoice("oversizedItems", "Choose Yes or No for oversized items."),
      ];
      return checks.every(Boolean);
    }
    return true;
  }

  function requireChoice(key, message) {
    if (state[key]) {
      clearError(key);
      return true;
    }
    setError(key, message);
    return false;
  }

  function validateSchedule() {
    const dateInput = document.getElementById("serviceDate");
    const timeInput = document.getElementById("pickupTime");
    if (!dateInput.value || !timeInput.value) {
      setError("schedule", "Choose both a date and time.");
      return false;
    }
    if (dateInput.value < todayValue) {
      setError("schedule", "The service date cannot be in the past.");
      dateInput.setAttribute("aria-invalid", "true");
      return false;
    }
    clearError("schedule");
    dateInput.removeAttribute("aria-invalid");
    return true;
  }

  function validateLocation() {
    const input = document.getElementById("locationInput");
    const value = input.value.trim();
    if (!value) {
      input.setAttribute("aria-invalid", "true");
      setError("locationInput", "Enter a ZIP Code or City.");
      return false;
    }
    if (/^\d+$/.test(value) && !/^\d{5}$/.test(value)) {
      input.setAttribute("aria-invalid", "true");
      setError("locationInput", "Enter a 5-digit ZIP Code or a City name.");
      return false;
    }
    input.removeAttribute("aria-invalid");
    clearError("locationInput");
    return true;
  }

  function validateContact() {
    const phone = document.getElementById("customerPhone");
    const email = document.getElementById("customerEmail");
    const hasPhone = Boolean(phone.value.trim());
    const hasEmail = Boolean(email.value.trim());
    phone.removeAttribute("aria-invalid");
    email.removeAttribute("aria-invalid");

    if (!state.contactMethod) {
      setError("contactMethod", "Choose Text message or Email.");
      return false;
    }
    clearError("contactMethod");
    if (!hasPhone && !hasEmail) {
      phone.setAttribute("aria-invalid", "true");
      email.setAttribute("aria-invalid", "true");
      setError("contact", "Enter a phone number or email address.");
      return false;
    }
    if (state.contactMethod === "TEXT" && !hasPhone) {
      phone.setAttribute("aria-invalid", "true");
      setError("contact", "Enter a phone number for text message contact.");
      return false;
    }
    if (state.contactMethod === "EMAIL" && !hasEmail) {
      email.setAttribute("aria-invalid", "true");
      setError("contact", "Enter an email address for email contact.");
      return false;
    }
    if (hasEmail && !email.checkValidity()) {
      email.setAttribute("aria-invalid", "true");
      setError("contact", "Enter a valid email address.");
      return false;
    }
    clearError("contact");
    return true;
  }

  async function loadEstimate() {
    clearError("estimateRequest");
    setEstimateLoading(true);
    try {
      const tripData = collectTripData();
      const estimate = await requestEstimate(tripData);
      state.estimateId = estimate.estimate_id;
      renderEstimate(estimate, tripData);
      showStep(6);
    } catch (error) {
      setError("estimateRequest", estimateErrorMessage(error));
    } finally {
      setEstimateLoading(false);
    }
  }

  function collectTripData() {
    return {
      serviceType: state.serviceType,
      airportCode: state.airportCode,
      date: document.getElementById("serviceDate").value,
      time: document.getElementById("pickupTime").value,
      location: document.getElementById("locationInput").value.trim(),
      passengers: state.passengerCount,
      luggage: state.luggageCount,
      childSeat: state.childSeat,
      oversizedItems: state.oversizedItems,
    };
  }

  async function requestEstimate(tripData) {
    const payload = {
      service_type: tripData.serviceType,
      airport_code: tripData.airportCode,
      service_date: tripData.date,
      service_time: tripData.time,
      service_timezone: "America/Los_Angeles",
      location_input: tripData.location,
      passenger_count: tripData.passengers,
      large_luggage_count: tripData.luggage,
      child_seat_required: tripData.childSeat === "YES",
      oversized_items: tripData.oversizedItems === "YES",
    };

    let response;
    try {
      response = await fetch("/api/v1/quote-estimates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch (error) {
      throw new EstimateRequestError("NETWORK_ERROR", "Unable to connect. Check your internet connection and try again.");
    }

    const responseBody = await readJsonResponse(response);
    if (!response.ok) {
      if (response.status === 422) {
        throw new EstimateRequestError("VALIDATION_ERROR", validationMessage(responseBody));
      }
      if (response.status === 400) {
        throw new EstimateRequestError(
          responseBody?.error?.code || "BUSINESS_ERROR",
          responseBody?.error?.message || "Jason cannot estimate this trip yet. Please review your details."
        );
      }
      throw new EstimateRequestError("SERVER_ERROR", "The estimate service is temporarily unavailable. Please try again.");
    }
    return responseBody;
  }

  function renderEstimate(estimate, tripData) {
    const manualReviewRequired = estimate.status === "MANUAL_REVIEW_REQUIRED";
    const rangeElement = document.getElementById("estimateRange");
    const manualReview = document.getElementById("manualReview");
    const acceptButton = document.getElementById("acceptEstimateButton");
    rangeElement.textContent = manualReviewRequired
      ? "Manual review required."
      : `${formatUsd(estimate.estimated_min_amount)} - ${formatUsd(estimate.estimated_max_amount)}`;
    rangeElement.hidden = manualReviewRequired;
    manualReview.hidden = !manualReviewRequired;
    acceptButton.textContent = manualReviewRequired ? "Continue for Jason Review" : "Accept Estimate Range";
    document.getElementById("estimateRoute").textContent = estimate.route_summary;

    const summary = [
      ["Passengers", tripData.passengers],
      ["Luggage", tripData.luggage],
      ["Child seat", tripData.childSeat === "YES" ? "Requested — Jason confirmation required" : "No"],
      ["Vehicle assessment", displayVehicleAssessment(estimate.vehicle_assessment)],
      ["Date & time", `${tripData.date} · ${formatTime(tripData.time)}`],
    ];
    if (estimate.risk_flags?.length) {
      summary.push(["Review flags", estimate.risk_flags.map(displayRiskFlag).join(", ")]);
    }
    document.getElementById("estimateSummary").innerHTML = summary
      .map(([label, value]) => `<div><dt>${label}</dt><dd>${escapeHtml(value)}</dd></div>`)
      .join("");

    const notices = Array.isArray(estimate.notices) ? [...estimate.notices] : [];
    if (tripData.childSeat === "YES") {
      notices.push("Child seat availability requires Jason confirmation.");
    }
    document.getElementById("estimateNotices").innerHTML = notices
      .map((notice) => `<p>${escapeHtml(notice)}</p>`)
      .join("");
    document.getElementById("estimateValidity").textContent = formatEstimateValidity(estimate.valid_until);
  }

  function setEstimateLoading(loading) {
    continueButton.disabled = loading;
    continueButton.textContent = loading ? "Getting estimate…" : "Continue";
    form.setAttribute("aria-busy", String(loading));
  }

  async function readJsonResponse(response) {
    try {
      return await response.json();
    } catch (error) {
      throw new EstimateRequestError("INVALID_RESPONSE", "The estimate service returned an invalid response. Please try again.");
    }
  }

  function validationMessage(responseBody) {
    const firstError = Array.isArray(responseBody?.detail) ? responseBody.detail[0] : null;
    return firstError?.msg || "Please review the trip details and try again.";
  }

  function estimateErrorMessage(error) {
    if (error instanceof EstimateRequestError) return error.message;
    return "Unable to get an estimate right now. Please try again.";
  }

  function formatUsd(value) {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return "—";
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(amount);
  }

  function displayVehicleAssessment(value) {
    return {
      LIKELY_COMFORTABLE: "Likely comfortable",
      NEEDS_CONFIRMATION: "Needs confirmation",
      NOT_RECOMMENDED: "Not recommended",
      INSUFFICIENT_INFORMATION: "Needs more information",
    }[value] || "Jason review required";
  }

  function displayRiskFlag(value) {
    return {
      PASSENGER_COUNT_5_PLUS: "5+ passengers",
      LARGE_LUGGAGE_4_PLUS: "4+ large luggage",
      OVERSIZED_ITEMS: "Oversized items",
      UNKNOWN_LOCATION: "Location review",
    }[value] || String(value).replaceAll("_", " ").toLowerCase();
  }

  function updateLocationLabel() {
    const isDropoff = state.serviceType === "AIRPORT_DROPOFF";
    document.getElementById("locationLabel").textContent = isDropoff
      ? "Pickup ZIP Code or City"
      : "Destination ZIP Code or City";
    document.getElementById("dateLabel").textContent = isDropoff
      ? "Pickup Date"
      : "Flight Arrival Date";
    document.getElementById("timeLabel").textContent = isDropoff
      ? "Pickup Time"
      : "Flight Arrival Time";
    document.getElementById("scheduleGuidance").textContent = isDropoff
      ? "When would you like Jason to pick you up?"
      : "Enter your scheduled flight arrival time.";
  }

  function formatTime(value) {
    const [hourText, minute] = value.split(":");
    const hour = Number(hourText);
    const suffix = hour >= 12 ? "PM" : "AM";
    return `${hour % 12 || 12}:${minute} ${suffix}`;
  }

  function dateInTimeZone(timeZone) {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).formatToParts(Date.now());
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${values.year}-${values.month}-${values.day}`;
  }

  function formatEstimateValidity(validUntil) {
    const parsed = Date.parse(validUntil);
    if (!Number.isFinite(parsed)) {
      return "Estimate validity is unavailable. Final price requires Jason confirmation.";
    }
    const formatted = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    }).format(parsed);
    return `Estimate valid until ${formatted}. Vehicle availability and final price are not guaranteed until Jason confirms.`;
  }

  class EstimateRequestError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "EstimateRequestError";
      this.code = code;
    }
  }

  function setError(key, message) {
    const target = form.querySelector(`[data-error-for="${key}"]`);
    if (target) target.textContent = message;
  }

  function clearError(key) {
    setError(key, "");
  }

  function escapeHtml(value) {
    const element = document.createElement("span");
    element.textContent = String(value);
    return element.innerHTML;
  }

  function resetPrototype() {
    form.reset();
    Object.assign(state, {
      serviceType: null,
      airportCode: null,
      passengerCount: null,
      luggageCount: null,
      childSeat: null,
      oversizedItems: null,
      contactMethod: null,
      estimateAccepted: false,
      estimateId: null,
    });
    form.querySelectorAll(".is-selected").forEach((button) => button.classList.remove("is-selected"));
    form.querySelectorAll("[aria-pressed]").forEach((button) => button.setAttribute("aria-pressed", "false"));
    form.querySelectorAll(".field-error").forEach((error) => { error.textContent = ""; });
    form.hidden = false;
    document.querySelector(".quote-progress").hidden = false;
    successPanel.hidden = true;
    showStep(1);
  }

  showStep(1);
})();
