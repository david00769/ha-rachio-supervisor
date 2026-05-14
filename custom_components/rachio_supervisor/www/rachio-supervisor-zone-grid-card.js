class RachioSupervisorZoneGridCard extends HTMLElement {
  setConfig(config) {
    this.config = {
      entity: "sensor.rachio_site_zone_overview",
      health_entity: "sensor.rachio_site_health",
      webhook_entity: "sensor.rachio_site_webhook_health",
      catch_up_entity: "sensor.rachio_site_catch_up_evidence",
      moisture_entity: "sensor.rachio_site_recommended_moisture_writes",
      flow_entity: "sensor.rachio_site_active_flow_alerts",
      calibration_entities: {},
      auto_detect_calibration_entities: true,
      title: "Zones",
      show_disabled_photo_status: false,
      ...config,
    };
    this._durations = this._durations || new Map();
    this._calibrationTargets = this._calibrationTargets || new Map();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 5;
  }

  _render() {
    if (!this._hass || !this.config) {
      return;
    }
    const stateObj = this._hass.states[this.config.entity];
    const zones = Array.isArray(stateObj?.attributes?.zones)
      ? stateObj.attributes.zones
      : [];
    const supervisor = this._supervisorState();
    this._zones = zones;
    this.innerHTML = `
      <ha-card>
        <style>
          :host {
            display: block;
          }
          .wrap {
            padding: 16px;
          }
          .title {
            font-size: 1.15rem;
            font-weight: 650;
            margin: 0 0 14px;
          }
          .supervisor {
            display: grid;
            gap: 8px;
            margin: 0 0 14px;
            padding: 10px 12px;
            border: 1px solid var(--divider-color, rgba(0,0,0,.12));
            border-left: 2px solid var(--success-color, #6fcf97);
            border-radius: 9px;
            background: color-mix(in srgb, var(--ha-card-background, var(--card-background-color, #ffffff)) 96%, var(--success-color, #6fcf97) 4%);
          }
          .supervisor.attention {
            border-left-color: var(--warning-color, #f7c948);
            background: color-mix(in srgb, var(--ha-card-background, var(--card-background-color, #ffffff)) 88%, var(--warning-color, #f7c948) 12%);
          }
          .supervisor.issue {
            border-left-color: var(--error-color, #ff6b6b);
            background: color-mix(in srgb, var(--ha-card-background, var(--card-background-color, #ffffff)) 88%, var(--error-color, #ff6b6b) 12%);
          }
          .supervisor-main {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            min-width: 0;
          }
          .supervisor-title {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            min-width: 0;
            color: var(--secondary-text-color);
            font-weight: 650;
          }
          .supervisor.attention .supervisor-title,
          .supervisor.issue .supervisor-title {
            color: var(--primary-text-color);
          }
          .supervisor-title ha-icon {
            width: 18px;
            height: 18px;
          }
          .supervisor-title span {
            overflow-wrap: anywhere;
          }
          .supervisor-pills {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 8px;
            flex-wrap: wrap;
          }
          .supervisor-note {
            color: var(--secondary-text-color);
            font-size: .82rem;
            line-height: 1.35;
          }
          .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 12px;
          }
          .zone {
            overflow: hidden;
            border: 1px solid var(--divider-color, rgba(0,0,0,.14));
            border-radius: 10px;
            background: var(--ha-card-background, var(--card-background-color, #ffffff));
            color: var(--primary-text-color, #17201b);
          }
          .photo {
            position: relative;
            min-height: 148px;
            overflow: hidden;
            background:
              linear-gradient(135deg, rgba(43,73,53,.92), rgba(104,126,92,.82)),
              radial-gradient(circle at 78% 12%, rgba(255,255,255,.22), transparent 30%);
          }
          .photo::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
              linear-gradient(180deg, rgba(255,255,255,.06), rgba(0,0,0,.22)),
              repeating-linear-gradient(120deg, rgba(255,255,255,.06) 0 1px, transparent 1px 18px);
          }
          .photo img {
            width: 100%;
            height: 168px;
            object-fit: cover;
            display: block;
            color: transparent;
            background: transparent;
            position: relative;
            z-index: 1;
          }
          .photo img[hidden] {
            display: none;
          }
          .photo-error {
            position: relative;
            z-index: 1;
            height: 168px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 6px;
            color: white;
            text-align: center;
            font-size: .92rem;
            font-weight: 700;
            text-transform: lowercase;
            text-shadow: 0 1px 2px rgba(0,0,0,.48);
          }
          .photo-error ha-icon {
            width: 26px;
            height: 26px;
            opacity: .92;
          }
          .shade {
            position: absolute;
            inset: 0;
            z-index: 2;
            background: linear-gradient(180deg, rgba(0,0,0,.08), rgba(0,0,0,.58));
          }
          .zone-name {
            position: absolute;
            left: 12px;
            right: 12px;
            bottom: 12px;
            z-index: 3;
            color: white;
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.15;
            overflow-wrap: anywhere;
            text-shadow: 0 1px 2px rgba(0,0,0,.5);
          }
          .photo-status {
            position: absolute;
            left: 10px;
            right: 10px;
            top: 10px;
            z-index: 3;
            display: flex;
            justify-content: flex-start;
            gap: 8px;
            align-items: flex-start;
            flex-wrap: wrap;
          }
          .body {
            padding: 12px;
            display: grid;
            gap: 10px;
            background: color-mix(in srgb, var(--ha-card-background, var(--card-background-color, #ffffff)) 96%, #6d7d6e 4%);
          }
          .badges, .days, .actions {
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
          }
          .badges {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
          }
          .badge, .day {
            display: inline-flex;
            gap: 6px;
            align-items: center;
            min-height: 28px;
            min-width: 0;
            max-width: 100%;
            box-sizing: border-box;
            padding: 5px 12px;
            border-radius: 999px;
            background: var(--secondary-background-color, rgba(127,127,127,.14));
            color: var(--primary-text-color);
            font-size: .8rem;
            line-height: 1.1;
            white-space: nowrap;
          }
          .badges .badge {
            width: 100%;
            min-width: 0;
            justify-content: flex-start;
          }
          .photo-status .badge {
            background: rgba(0, 0, 0, .52);
            color: white;
            backdrop-filter: blur(6px);
            min-width: 86px;
            max-width: 100%;
            justify-content: center;
          }
          .photo-status .badge.photo-diagnostic {
            margin-left: auto;
          }
          .badge ha-icon {
            --mdc-icon-size: 18px;
            flex: 0 0 18px;
            width: 18px;
            height: 18px;
          }
          .badge-label {
            flex: 1 1 auto;
            min-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .badge.warn {
            color: var(--warning-color, #f7c948);
          }
          .badge.issue {
            color: var(--error-color, #ff6b6b);
          }
          .badge.ok {
            color: var(--success-color, #6fcf97);
          }
          .badge.muted {
            color: var(--secondary-text-color);
          }
          .next {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            min-width: 0;
            color: var(--secondary-text-color);
            font-size: .86rem;
          }
          .next strong {
            color: var(--primary-text-color);
            font-weight: 650;
            overflow-wrap: anywhere;
          }
          .schedule {
            display: grid;
            grid-template-columns: auto 1fr;
            gap: 8px;
            align-items: center;
            min-width: 0;
            color: var(--secondary-text-color);
            font-size: .84rem;
          }
          .schedule ha-icon {
            width: 17px;
            height: 17px;
          }
          .schedule span {
            overflow-wrap: anywhere;
          }
          .day {
            min-width: 26px;
            justify-content: center;
            padding: 4px 6px;
            color: var(--secondary-text-color);
          }
          .day.on {
            color: var(--primary-text-color);
            background: color-mix(in srgb, var(--primary-color, #03a9f4) 30%, transparent);
          }
          .note {
            color: var(--secondary-text-color);
            font-size: .84rem;
            line-height: 1.35;
            overflow-wrap: anywhere;
          }
          .actions {
            justify-content: space-between;
            border-top: 1px solid var(--divider-color, rgba(255,255,255,.12));
            padding-top: 10px;
          }
          .minutes {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: var(--secondary-text-color);
            font-size: .82rem;
          }
          input {
            width: 54px;
            box-sizing: border-box;
            border: 1px solid var(--divider-color, rgba(255,255,255,.2));
            border-radius: 6px;
            padding: 6px 4px;
            background: var(--card-background-color, #ffffff);
            color: var(--primary-text-color, #17201b);
            text-align: center;
          }
          .calibration {
            display: grid;
            gap: 8px;
            margin-top: 4px;
            padding-top: 8px;
            border-top: 1px solid var(--divider-color, rgba(255,255,255,.12));
          }
          .calibration-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            color: var(--primary-text-color);
            font-weight: 650;
          }
          .calibration-head small {
            color: var(--secondary-text-color);
            font-weight: 500;
          }
          .calibration-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
            align-items: end;
          }
          .calibration-field {
            display: grid;
            gap: 4px;
            min-width: 0;
          }
          .calibration-field span {
            color: var(--secondary-text-color);
            font-size: .76rem;
          }
          .calibration-field strong,
          .calibration-field output {
            color: var(--primary-text-color);
            font-size: .9rem;
            font-weight: 650;
            min-height: 31px;
            display: inline-flex;
            align-items: center;
          }
          .calibration-field input {
            width: 100%;
            min-width: 0;
          }
          .calibration-actions {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            min-width: 0;
          }
          .calibration-actions code {
            color: var(--secondary-text-color);
            font-size: .74rem;
            overflow-wrap: anywhere;
          }
          .calibration-actions button {
            white-space: nowrap;
          }
          button {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            min-height: 34px;
            border: 0;
            border-radius: 8px;
            padding: 0 12px;
            background: var(--primary-color, #03a9f4);
            color: var(--text-primary-color, white);
            font-weight: 650;
            cursor: pointer;
          }
          button[disabled] {
            opacity: .46;
            cursor: not-allowed;
          }
          button.running {
            background: var(--secondary-text-color);
          }
          details {
            color: var(--secondary-text-color);
            font-size: .82rem;
          }
          summary {
            cursor: pointer;
            color: var(--primary-text-color);
          }
          .detail {
            margin-top: 8px;
            display: grid;
            gap: 6px;
            line-height: 1.35;
          }
          .detail-row {
            display: grid;
            grid-template-columns: 76px 1fr;
            gap: 10px;
          }
          .detail-row span:first-child {
            color: var(--secondary-text-color);
          }
          .detail-row span:last-child {
            color: var(--primary-text-color);
            overflow-wrap: anywhere;
          }
          .empty {
            color: var(--secondary-text-color);
            padding: 12px 0 4px;
          }
          @media (max-width: 520px) {
            .wrap {
              padding: 12px;
            }
            .supervisor-main {
              align-items: flex-start;
              flex-direction: column;
            }
            .supervisor-pills {
              justify-content: flex-start;
            }
            .grid {
              grid-template-columns: 1fr;
            }
            .photo img {
              height: 156px;
            }
            .calibration-grid {
              grid-template-columns: 1fr;
            }
            .calibration-actions {
              align-items: flex-start;
              flex-direction: column;
            }
          }
        </style>
        <div class="wrap">
          <div class="title">${this._escape(this.config.title)}</div>
          ${this._supervisorTemplate(supervisor)}
          ${
            zones.length
              ? `<div class="grid">${zones.map((zone, index) => this._zoneTemplate(zone, index)).join("")}</div>`
              : `<div class="empty">No Rachio zones discovered yet.</div>`
          }
        </div>
      </ha-card>
    `;
    this._bindActions();
  }

  _supervisorState() {
    const health = this._state(this.config.health_entity);
    const webhook = this._state(this.config.webhook_entity);
    const catchUp = this._state(this.config.catch_up_entity);
    const moisture = this._state(this.config.moisture_entity);
    const flow = this._state(this.config.flow_entity);
    const missingInputs = health.attributes?.missing_inputs || [];
    const reason = health.attributes?.supervisor_reason || health.state || "not reported";
    const moistureCount = Number.parseInt(moisture.state || "0", 10) || 0;
    const flowCount = Number.parseInt(flow.state || "0", 10) || 0;
    const catchUpState = catchUp.attributes?.status || catchUp.state || "none";
    const catchUpEvidence = catchUp.attributes?.evidence_label || catchUp.state || "";
    const catchUpAction = catchUp.attributes?.action_label || "";
    const healthState = health.state || "unknown";
    const webhookState = webhook.state || "unknown";
    const unknown = ["unknown", "unavailable"].includes(healthState)
      || ["unknown", "unavailable"].includes(webhookState);
    const issue = healthState === "degraded" || webhookState === "degraded";
    const attention = issue
      || unknown
      || moistureCount > 0
      || flowCount > 0
      || !["none", "not_needed", "monitoring", "unknown", "unavailable"].includes(catchUpState);
    return {
      issue,
      attention,
      unknown,
      healthState,
      webhookState,
      catchUpState,
      catchUpEvidence,
      catchUpAction,
      moistureCount,
      flowCount,
      reason,
      missingInputs,
    };
  }

  _state(entityId) {
    return this._hass?.states?.[entityId] || { state: "unknown", attributes: {} };
  }

  _supervisorTemplate(supervisor) {
    const tone = supervisor.issue ? "issue" : supervisor.attention ? "attention" : "";
    const title = supervisor.issue
      ? "Supervisor needs review"
      : supervisor.unknown
        ? "Supervisor not ready"
        : supervisor.attention
          ? "Supervisor has actions"
          : "Supervisor ok";
    const icon = supervisor.issue
      ? "mdi:alert-circle-outline"
      : supervisor.unknown
        ? "mdi:progress-clock"
        : supervisor.attention
          ? "mdi:bell-ring-outline"
          : "mdi:shield-check-outline";
    const note = this._supervisorNote(supervisor);
    return `
      <div class="supervisor ${tone}">
        <div class="supervisor-main">
          <div class="supervisor-title">
            <ha-icon icon="${icon}"></ha-icon>
            <span>${title}</span>
          </div>
          ${supervisor.attention ? this._supervisorPills(supervisor) : ""}
        </div>
        ${note ? `<div class="supervisor-note">${this._escape(note)}</div>` : ""}
      </div>
    `;
  }

  _supervisorPills(supervisor) {
    const pills = [];
    if (supervisor.issue || supervisor.unknown) {
      pills.push(this._badge("mdi:heart-pulse", this._compactState(supervisor.healthState), supervisor.issue ? "issue" : "warn", `Health: ${supervisor.healthState}`));
      pills.push(this._badge("mdi:webhook", this._compactState(supervisor.webhookState), supervisor.webhookState === "degraded" ? "issue" : "warn", `Webhook: ${supervisor.webhookState}`));
    }
    if (!["none", "not_needed", "monitoring", "unknown", "unavailable"].includes(supervisor.catchUpState)) {
      pills.push(this._badge("mdi:sprinkler-variant", this._catchUpLabel(supervisor.catchUpState), this._catchUpTone(supervisor.catchUpState), `Catch-up: ${supervisor.catchUpState}`));
    }
    if (supervisor.moistureCount > 0) {
      pills.push(this._badge("mdi:water-percent-alert", String(supervisor.moistureCount), "warn", `Recommended moisture writes: ${supervisor.moistureCount}`));
    }
    if (supervisor.flowCount > 0) {
      pills.push(this._badge("mdi:pipe-leak", String(supervisor.flowCount), "issue", `Active flow alerts: ${supervisor.flowCount}`));
    }
    if (Array.isArray(supervisor.missingInputs) && supervisor.missingInputs.length && !supervisor.issue && !supervisor.unknown) {
      pills.push(this._badge("mdi:database-alert-outline", String(supervisor.missingInputs.length), "warn", this._dataWarningDetail(supervisor.missingInputs)));
    }
    return `
      <div class="supervisor-pills">
        ${pills.join("")}
      </div>
    `;
  }

  _supervisorNote(supervisor) {
    if (supervisor.issue) {
      return supervisor.reason;
    }
    if (supervisor.unknown) {
      return "Supervisor entities are not reporting yet.";
    }
    if (Array.isArray(supervisor.missingInputs) && supervisor.missingInputs.length) {
      return this._dataWarningSummary(supervisor.missingInputs);
    }
    if (supervisor.flowCount > 0) {
      return "Flow alert review is active.";
    }
    if (supervisor.moistureCount > 0) {
      return "Moisture writes are recommended.";
    }
    if (!["none", "not_needed", "monitoring", "unknown", "unavailable"].includes(supervisor.catchUpState)) {
      return supervisor.catchUpAction || supervisor.catchUpEvidence || `Catch-up review: ${supervisor.catchUpState}`;
    }
    return "";
  }

  _dataWarningSummary(inputs) {
    const warnings = this._dataWarnings(inputs);
    if (!warnings.length) {
      return "";
    }
    if (warnings.length === 1) {
      return warnings[0].summary;
    }
    return warnings.map((warning) => warning.short || warning.summary).join(" ");
  }

  _dataWarningDetail(inputs) {
    const warnings = this._dataWarnings(inputs);
    if (!warnings.length) {
      return "Data warnings";
    }
    return `Data warnings: ${warnings.map((warning) => warning.detail || warning.summary).join(" ")}`;
  }

  _dataWarnings(inputs) {
    const raw = Array.isArray(inputs) ? inputs : [];
    const moistureProblems = [];
    const otherWarnings = [];
    raw.forEach((input) => {
      const warning = String(input || "");
      const moisture = this._parseMoistureWarning(warning);
      if (moisture) {
        moistureProblems.push(moisture);
        return;
      }
      otherWarnings.push(this._humanDataWarning(warning));
    });
    const grouped = [];
    if (moistureProblems.length) {
      const zones = moistureProblems
        .map((problem) => problem.zone)
        .filter(Boolean);
      const reasons = [...new Set(moistureProblems.map((problem) => problem.reason).filter(Boolean))];
      const reason = reasons.length === 1 ? reasons[0] : "attention";
      const action = this._moistureProblemAction(reason);
      const count = zones.length || moistureProblems.length;
      grouped.push({
        short: `Moisture sensors need ${action} for ${count} ${count === 1 ? "zone" : "zones"}.`,
        summary: count === 1 && zones[0]
          ? `Moisture sensor for ${zones[0]} needs ${action}.`
          : `Moisture sensors need ${action} for ${count} zones. Check Moisture review below.`,
        detail: zones.length
          ? `Moisture sensors need ${action}: ${this._formatList(zones)}.`
          : `Moisture sensors need ${action}.`,
      });
    }
    otherWarnings.forEach((warning) => {
      if (warning) grouped.push(warning);
    });
    return grouped;
  }

  _parseMoistureWarning(warning) {
    const prefix = "moisture_sensor_problem:";
    if (!warning.startsWith(prefix)) {
      return null;
    }
    const body = warning.slice(prefix.length);
    const separator = body.lastIndexOf(":");
    if (separator < 0) {
      return { zone: body, reason: "attention" };
    }
    return {
      zone: body.slice(0, separator),
      reason: body.slice(separator + 1),
    };
  }

  _humanDataWarning(warning) {
    const labels = {
      no_active_schedule_moisture_mappings: "No active moisture sensor mappings are configured.",
      rain_actuals_unconfigured: "Observed rain source is not configured.",
      rain_actuals_missing: "Configured observed rain sensor is missing.",
      rain_actuals_unavailable: "Observed rain sensor is unavailable.",
      rain_actuals_rate_only: "Observed rain source reports rate only, not a rainfall total.",
      rain_actuals_weather_no_observed_precipitation: "Weather entity does not report observed rainfall.",
      rain_actuals_non_numeric: "Observed rain source is not reporting a number.",
      rain_actuals_weather_station_unconfigured: "Weather station source is not configured.",
      rain_actuals_weather_station_invalid: "Weather station ID is invalid.",
      rain_actuals_weather_station_api_key_missing: "Weather station API key is missing.",
      rain_actuals_weather_station_unavailable: "Weather station rainfall is unavailable.",
      rain_actuals_weather_station_precip_total_missing: "Weather station is not reporting a rainfall total.",
    };
    const label = labels[warning] || this._titleCase(warning.replaceAll("_", " "));
    return {
      short: label,
      summary: label,
      detail: label,
    };
  }

  _moistureProblemAction(reason) {
    const labels = {
      missing_sensor: "a mapped sensor",
      expired_sample: "a fresh check-in",
      stale_sample: "recent samples",
      sensor_sleeping_or_offline: "a fresh check-in",
      non_numeric_state: "numeric readings",
      boundary_value_needs_calibration: "calibration review",
      missing_companion_health_data: "sensor health context",
      attention: "attention",
    };
    return labels[reason] || this._titleCase(reason.replaceAll("_", " ")).toLowerCase();
  }

  _formatList(items) {
    const unique = [...new Set(items.filter(Boolean))];
    if (unique.length <= 2) {
      return unique.join(" and ");
    }
    return `${unique.slice(0, -1).join(", ")}, and ${unique[unique.length - 1]}`;
  }

  _titleCase(value) {
    return String(value || "")
      .split(" ")
      .filter(Boolean)
      .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
      .join(" ");
  }

  _zoneTemplate(zone, index) {
    const minutes = this._durationFor(zone, index);
    const days = Array.isArray(zone.watering_days) ? zone.watering_days : [];
    const canRun = Boolean(zone.zone_entity_id || zone.schedule_entity_id || zone.schedule_name);
    const imagePath = zone.image_path || zone.fallback_image_path || "";
    const fallbackPath = zone.fallback_image_path || "";
    const photoError = this._photoErrorLabel(zone);
    const calibration = this._calibrationState(zone);
    return `
      <section class="zone">
        <div class="photo">
          ${photoError ? this._photoErrorTemplate(zone, photoError) : `<img src="${this._escapeAttr(imagePath)}" data-fallback="${this._escapeAttr(fallbackPath)}" alt="${this._escapeAttr(zone.zone_name || "Rachio zone")}">`}
          <div class="shade"></div>
          <div class="photo-status">
            ${this._badge(zone.water_icon || "mdi:calendar-clock", zone.water_badge || "watch", this._waterTone(zone))}
            ${this._badge(zone.supervisor_icon || "mdi:check-circle-outline", zone.supervisor_badge || "ok", this._supervisorTone(zone))}
            ${this._photoBadge(zone)}
          </div>
          <div class="zone-name">${this._escape(zone.zone_name || "Rachio zone")}</div>
        </div>
        <div class="body">
          <div class="badges">
            ${this._badge("mdi:weather-rainy", this._rainLabel(zone), this._rainTone(zone))}
            ${this._badge("mdi:water-percent", this._moistureLabel(zone), this._moistureTone(zone), this._moistureTitle(zone))}
            ${this._badge("mdi:pipe-leak", this._flowLabel(zone), this._flowTone(zone))}
          </div>
          <div class="next">
            <span>Next</span>
            <strong>${this._escape(this._timeLabel(zone.next_run))}</strong>
          </div>
          <div class="schedule">
            <ha-icon icon="mdi:calendar-clock"></ha-icon>
            <span>${this._escape(zone.schedule_name || zone.zone_name || "Schedule")}</span>
          </div>
          <div class="days">${this._dayChips(days)}</div>
          <div class="note">${this._escape(zone.plant_note || "")}</div>
          <div class="actions">
            <label class="minutes">
              <span>Min</span>
              <input type="number" min="1" max="60" value="${minutes}" data-zone-index="${index}">
            </label>
            <button type="button" class="${this._pendingQuickRunIndex === index ? "running" : ""}" data-quick-run-index="${index}" ${canRun && this._pendingQuickRunIndex !== index ? "" : "disabled"}>
              <ha-icon icon="${this._pendingQuickRunIndex === index ? "mdi:progress-clock" : "mdi:play"}"></ha-icon>
              ${this._pendingQuickRunIndex === index ? "Starting" : "Quick Run"}
            </button>
          </div>
          <details>
            <summary>Details</summary>
            <div class="detail">
              ${this._detailRow("Notes", zone.detail_note || "No detail note configured.")}
              ${this._detailRow("Policy", zone.policy_mode || "unknown")}
              ${this._detailRow("Runtime", `${zone.runtime_minutes || minutes} min`)}
              ${this._detailRow("Last run", this._timeLabel(zone.last_run_at))}
              ${this._detailRow("Last skip", this._timeLabel(zone.last_skip_at, "none"))}
              ${this._detailRow("Moisture sensor", calibration.moistureEntity || zone.moisture_entity_id || "unmapped")}
              ${this._detailRow("Last check-in", this._moistureCheckInLabel(zone))}
              ${this._detailRow("Last valid moisture", this._moistureValueLabel(zone))}
              ${this._detailRow("Freshness", zone.moisture_freshness || "unknown")}
              ${this._detailRow("Confidence", zone.moisture_confidence || "none")}
              ${this._detailRow("Quality", zone.moisture_quality_note || "ok")}
              ${this._calibrationTemplate(zone, index, calibration)}
            </div>
          </details>
        </div>
      </section>
    `;
  }

  _bindActions() {
    this.querySelectorAll("img[data-fallback]").forEach((img) => {
      img.addEventListener("error", () => {
        const fallback = img.getAttribute("data-fallback");
        if (fallback && img.getAttribute("src") !== fallback) {
          img.setAttribute("src", fallback);
          return;
        }
        img.hidden = true;
      });
    });
    this.querySelectorAll("input[data-zone-index]").forEach((input) => {
      input.addEventListener("change", () => {
        const index = Number(input.getAttribute("data-zone-index"));
        this._durations.set(index, this._clampMinutes(input.value));
      });
    });
    this.querySelectorAll("input[data-calibration-target-index]").forEach((input) => {
      input.addEventListener("change", () => {
        const index = Number(input.getAttribute("data-calibration-target-index"));
        this._calibrationTargets.set(index, input.value);
        this._render();
      });
    });
    this.querySelectorAll("button[data-quick-run-index]").forEach((button) => {
      button.addEventListener("click", () => {
        this._quickRun(Number(button.getAttribute("data-quick-run-index")));
      });
    });
    this.querySelectorAll("button[data-apply-calibration-index]").forEach((button) => {
      button.addEventListener("click", () => {
        this._applyCalibration(Number(button.getAttribute("data-apply-calibration-index")));
      });
    });
  }

  async _quickRun(index) {
    const zone = this._zones?.[index];
    if (!zone || !this._hass) {
      return;
    }
    const input = this.querySelector(`input[data-zone-index="${index}"]`);
    const minutes = this._clampMinutes(input?.value || this._durationFor(zone, index));
    this._durations.set(index, minutes);
    const name = zone.zone_name || zone.schedule_name || "this zone";
    if (!window.confirm(`Run ${name} for ${minutes} minutes?`)) {
      return;
    }
    const data = {
      duration_minutes: minutes,
    };
    if (zone.zone_entity_id) {
      data.zone_entity_id = zone.zone_entity_id;
    }
    if (zone.schedule_entity_id) {
      data.schedule_entity_id = zone.schedule_entity_id;
    }
    if (zone.schedule_name) {
      data.schedule_name = zone.schedule_name;
    }
    this._pendingQuickRunIndex = index;
    this._render();
    try {
      await this._hass.callService("rachio_supervisor", "quick_run_zone", data);
      this._notify(`Started ${name} for ${minutes} minutes.`);
    } catch (error) {
      this._notify(`Quick Run failed: ${error?.message || error}`);
    } finally {
      this._pendingQuickRunIndex = undefined;
      this._render();
    }
  }

  async _applyCalibration(index) {
    const zone = this._zones?.[index];
    if (!zone || !this._hass) {
      return;
    }
    const calibration = this._calibrationState(zone);
    const suggested = this._suggestedCalibrationValue(calibration, this._calibrationTargets.get(index));
    if (!calibration.soilEntity || !Number.isFinite(suggested)) {
      return;
    }
    const name = zone.zone_name || zone.schedule_name || "this zone";
    if (!window.confirm(`Set ${name} soil calibration to ${this._formatCalibration(suggested)}?`)) {
      return;
    }
    this._pendingCalibrationIndex = index;
    this._render();
    try {
      await this._hass.callService("number", "set_value", {
        entity_id: calibration.soilEntity,
        value: suggested,
      });
      this._notify(`Updated ${name} soil calibration.`);
    } catch (error) {
      this._notify(`Calibration failed: ${error?.message || error}`);
    } finally {
      this._pendingCalibrationIndex = undefined;
      this._render();
    }
  }

  _durationFor(zone, index) {
    return this._clampMinutes(this._durations.get(index) || zone.quick_run_minutes || zone.runtime_minutes || 3);
  }

  _clampMinutes(value) {
    const parsed = Number.parseInt(value, 10);
    if (!Number.isFinite(parsed)) {
      return 3;
    }
    return Math.max(1, Math.min(60, parsed));
  }

  _dayChips(days) {
    const order = ["M", "T", "W", "Th", "F", "Sa", "Su"];
    return order
      .map((day) => `<span class="day ${days.includes(day) ? "on" : ""}">${day}</span>`)
      .join("");
  }

  _badge(icon, label, tone, title) {
    const safeTitle = this._escapeAttr(title || label);
    const toneClass = tone ? ` ${this._escapeAttr(tone)}` : "";
    return `<span class="badge${toneClass}" title="${safeTitle}" aria-label="${safeTitle}"><ha-icon icon="${this._escapeAttr(icon)}"></ha-icon><span class="badge-label">${this._escape(label)}</span></span>`;
  }

  _calibrationTemplate(zone, index, calibration = null) {
    calibration = calibration || this._calibrationState(zone);
    if (!calibration.soilEntity) {
      return "";
    }
    const targetValue = this._calibrationTargets.get(index) || "";
    const suggested = this._suggestedCalibrationValue(calibration, targetValue);
    const canApply = Number.isFinite(suggested) && this._pendingCalibrationIndex !== index;
    const pending = this._pendingCalibrationIndex === index;
    const source = calibration.source === "configured" ? "mapped" : "detected";
    return `
      <div class="calibration">
        <div class="calibration-head">
          <span>Calibration</span>
          <small>${source}</small>
        </div>
        <div class="calibration-grid">
          <label class="calibration-field">
            <span>Current</span>
            <strong>${this._escape(this._percentLabel(calibration.currentValue))}</strong>
          </label>
          <label class="calibration-field">
            <span>Target</span>
            <input type="number" min="0" max="100" step="1" inputmode="decimal" value="${this._escapeAttr(targetValue)}" placeholder="%" data-calibration-target-index="${index}">
          </label>
          <label class="calibration-field">
            <span>Offset</span>
            <output>${this._escape(Number.isFinite(suggested) ? this._formatCalibration(suggested) : this._formatCalibration(calibration.currentOffset))}</output>
          </label>
        </div>
        <div class="calibration-actions">
          <code>${this._escape(calibration.soilEntity)}</code>
          <button type="button" class="${pending ? "running" : ""}" data-apply-calibration-index="${index}" ${canApply ? "" : "disabled"}>
            <ha-icon icon="${pending ? "mdi:progress-clock" : "mdi:tune-variant"}"></ha-icon>
            ${pending ? "Applying" : "Apply Offset"}
          </button>
        </div>
      </div>
    `;
  }

  _calibrationState(zone) {
    const configured = this._configuredCalibrationEntities(zone);
    const detected = configured.soilEntity
      ? {}
      : this.config.auto_detect_calibration_entities === false
        ? {}
        : this._detectedCalibrationEntities(zone, configured.moistureEntity);
    const soilEntity = configured.soilEntity || detected.soilEntity || "";
    const moistureEntity = configured.moistureEntity || detected.moistureEntity || zone.moisture_entity_id || "";
    const soilState = soilEntity ? this._state(soilEntity) : { state: "unknown", attributes: {} };
    const moistureState = moistureEntity ? this._state(moistureEntity) : null;
    const fallbackMoisture = this._parseNumber(zone.moisture_observed_value || zone.moisture_value || zone.moisture_source_state);
    return {
      soilEntity,
      moistureEntity,
      source: configured.soilEntity ? "configured" : "detected",
      currentValue: this._parseNumber(moistureState?.state, fallbackMoisture),
      currentOffset: this._parseNumber(soilState.state),
      min: this._parseNumber(soilState.attributes?.min, -30),
      max: this._parseNumber(soilState.attributes?.max, 30),
    };
  }

  _configuredCalibrationEntities(zone) {
    const map = this.config.calibration_entities || {};
    const keys = [
      zone.schedule_entity_id,
      zone.moisture_entity_id,
      zone.zone_entity_id,
      zone.schedule_name,
      zone.zone_name,
    ].filter(Boolean);
    for (const key of keys) {
      const value = map[key];
      if (!value) {
        continue;
      }
      if (typeof value === "string") {
        return { soilEntity: value };
      }
      return {
        soilEntity: value.soil || value.soil_calibration || value.calibration_entity || "",
        moistureEntity: value.moisture || value.moisture_entity || value.moisture_entity_id || "",
      };
    }
    return {};
  }

  _detectedCalibrationEntities(zone, moistureEntity = "") {
    const soilEntity = this._findNumberEntity(zone, ["soil_calibration", "soil calibration"], moistureEntity);
    return soilEntity ? { soilEntity, moistureEntity: moistureEntity || zone.moisture_entity_id || "" } : {};
  }

  _findNumberEntity(zone, markers, moistureEntity = "") {
    const tokenSet = this._zoneMoistureTokens(zone, moistureEntity);
    if (!tokenSet.size) {
      return "";
    }
    const candidates = Object.entries(this._hass?.states || {})
      .filter(([entityId]) => entityId.startsWith("number."))
      .map(([entityId, state]) => {
        const label = `${entityId} ${state.attributes?.friendly_name || ""}`.toLowerCase();
        if (!markers.some((marker) => label.includes(marker))) {
          return null;
        }
        const candidateTokens = this._tokens(label);
        let score = 0;
        tokenSet.forEach((token) => {
          if (candidateTokens.has(token)) {
            score += 1;
          }
        });
        return { entityId, score };
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score);
    if (!candidates.length || candidates[0].score <= 0) {
      return "";
    }
    if (candidates[1] && candidates[1].score === candidates[0].score) {
      return "";
    }
    return candidates[0].entityId;
  }

  _zoneMoistureTokens(zone, moistureEntity = "") {
    moistureEntity = moistureEntity || zone.moisture_entity_id || "";
    const moistureState = moistureEntity ? this._state(moistureEntity) : null;
    return this._tokens([
      moistureEntity,
      moistureState?.attributes?.friendly_name || "",
    ].join(" "));
  }

  _tokens(value) {
    const stopWords = new Set([
      "sensor", "number", "soil", "moisture", "calibration", "temperature",
      "humidity", "sampling", "warning", "dry", "battery", "linkquality",
    ]);
    const tokens = String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, " ")
      .split(" ")
      .filter((token) => token.length > 1 && !stopWords.has(token));
    return new Set(tokens);
  }

  _suggestedCalibrationValue(calibration, targetValue) {
    const target = this._parseNumber(targetValue);
    if (!Number.isFinite(target) || !Number.isFinite(calibration.currentValue)) {
      return Number.NaN;
    }
    const next = calibration.currentOffset + (target - calibration.currentValue);
    return Math.max(calibration.min, Math.min(calibration.max, Math.round(next)));
  }

  _parseNumber(value, fallback = Number.NaN) {
    if (value === undefined || value === null || value === "" || value === "unknown" || value === "unavailable") {
      return fallback;
    }
    const parsed = Number.parseFloat(String(value).replace("%", ""));
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  _percentLabel(value) {
    if (!Number.isFinite(value)) {
      return "none";
    }
    const rounded = Math.round(value * 10) / 10;
    return `${rounded}%`;
  }

  _formatCalibration(value) {
    if (!Number.isFinite(value)) {
      return "unknown";
    }
    const rounded = Math.round(value * 10) / 10;
    return rounded > 0 ? `+${rounded}%` : `${rounded}%`;
  }

  _photoBadge(zone) {
    const source = zone.image_source || "";
    const status = zone.photo_import_status || "";
    if (source === "local_override" || source === "rachio_import") {
      return "";
    }
    if (status === "missing") {
      return this._badge("mdi:image-off-outline", "No photo", "muted photo-diagnostic", this._photoTitle(zone));
    }
    if (status === "disabled" && this.config.show_disabled_photo_status) {
      return this._badge("mdi:image-outline", "photos off", "muted photo-diagnostic", this._photoTitle(zone));
    }
    return "";
  }

  _photoErrorTemplate(zone, label) {
    const title = this._photoTitle(zone);
    return `
      <div class="photo-error" role="status" aria-label="${this._escapeAttr(label)}" title="${this._escapeAttr(title)}">
        <ha-icon icon="mdi:image-off-outline"></ha-icon>
        <span>${this._escape(label)}</span>
      </div>
    `;
  }

  _photoErrorLabel(zone) {
    const source = zone.image_source || "";
    if (source === "local_override" || source === "rachio_import") {
      return "";
    }
    const status = zone.photo_import_status || "";
    const reason = zone.photo_import_reason || "";
    if (status === "rejected" && reason === "image_too_large") return "image too large";
    if (status === "rejected" && reason === "resized_image_too_large") return "image too large";
    if (status === "rejected" && reason === "pillow_unavailable_for_resize") return "resize unavailable";
    if (status === "rejected" && reason.startsWith("image_decode_failed")) return "image unreadable";
    if (status === "rejected" && reason.startsWith("unsupported_content_type")) return "unsupported image";
    if (status === "rejected") return "image unavailable";
    if (status === "failed") return "image unavailable";
    return "";
  }

  _photoTitle(zone) {
    const status = zone.photo_import_status || "unknown";
    const reason = zone.photo_import_reason || "";
    if (status === "rejected" && ["image_too_large", "resized_image_too_large"].includes(reason)) {
      return "Rachio photo is larger than the dashboard import limit after resizing, so the card hides the image. Add a local zone photo to replace it.";
    }
    if (status === "rejected" && reason === "pillow_unavailable_for_resize") {
      return "Rachio photo needs resizing, but the Home Assistant image library is unavailable. Add a local zone photo to replace it.";
    }
    if (status === "rejected" && reason.startsWith("image_decode_failed")) {
      return "Rachio photo could not be decoded, so the card hides the image. Add a local zone photo to replace it.";
    }
    if (status === "rejected" && reason.startsWith("unsupported_content_type")) {
      return "Rachio photo is not a supported image type, so the card hides the image. Add a local zone photo to replace it.";
    }
    if (status === "failed") {
      return `Rachio photo import failed${reason ? `: ${reason}` : ""}. The card hides the image.`;
    }
    return `Photo import ${status}${reason ? `: ${reason}` : ""}`;
  }

  _compactState(value) {
    const state = String(value || "unknown").replace(/_/g, " ");
    if (state === "healthy") return "ok";
    if (state === "degraded") return "bad";
    if (state === "not reported") return "?";
    return state;
  }

  _catchUpLabel(value) {
    const state = String(value || "none");
    if (["none", "not_needed", "monitoring", "unknown", "unavailable"].includes(state)) {
      return "catch-up";
    }
    if (state.includes("eligible")) return "ready";
    if (state.includes("review")) return "review";
    return "catch-up";
  }

  _catchUpTone(value) {
    const state = String(value || "none");
    if (["none", "not_needed", "monitoring", "unknown", "unavailable"].includes(state)) {
      return "muted";
    }
    if (state.includes("eligible")) return "warn";
    if (state.includes("review")) return "warn";
    return "warn";
  }

  _detailRow(label, value) {
    return `<div class="detail-row"><span>${this._escape(label)}</span><span>${this._escape(value)}</span></div>`;
  }

  _timeLabel(value, fallback = "not reported") {
    if (!value || value === "not_reported") {
      return fallback;
    }
    const text = String(value);
    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) {
      return text;
    }
    const day = parsed.toLocaleDateString(undefined, { weekday: "short" });
    const time = parsed.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "2-digit",
    });
    return `${day} ${time}`;
  }

  _notify(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message },
      bubbles: true,
      composed: true,
    }));
  }

  _waterTone(zone) {
    if (zone.water_badge === "skip") return "warn";
    if (zone.water_badge === "watered") return "ok";
    return "";
  }

  _rainLabel(zone) {
    const state = zone.rain_skip_state || "none";
    if (state === "none") return "rain";
    if (state === "skipped_rain_satisfied") return "skip";
    if (state === "skipped_rain_shortfall") return "review";
    if (state === "skipped_unknown_rain") return "skip ?";
    return "skip";
  }

  _rainTone(zone) {
    if (zone.rain_skip_state === "none") return "muted";
    if (zone.rain_skip_state === "skipped_rain_shortfall") return "issue";
    return "warn";
  }

  _moistureTone(zone) {
    if (zone.moisture_quality_note === "boundary_value_needs_calibration") return "warn";
    if (["stale", "expired"].includes(zone.moisture_freshness)) return "muted";
    if (["missing_sensor", "sensor_sleeping_or_offline"].includes(zone.moisture_quality_note)) return "muted";
    if (zone.moisture_band === "dry") return "issue";
    if (zone.moisture_band === "wet") return "warn";
    if (zone.moisture_band === "target") return "ok";
    return "";
  }

  _moistureLabel(zone) {
    const note = zone.moisture_quality_note || "";
    if (note === "boundary_value_needs_calibration") return "calibrate";
    if (note === "missing_sensor") return "no sensor";
    if (zone.moisture_freshness === "expired") return "no sample";
    if (zone.moisture_freshness === "stale") return "stale";
    const value = zone.moisture_observed_value || zone.moisture_value;
    const age = zone.moisture_age_label;
    if (value) {
      return age && age !== "unknown" ? `${value}% \u00b7 ${age}` : `${value}%`;
    }
    if (zone.moisture_band && !["unmapped", "missing"].includes(zone.moisture_band)) {
      return zone.moisture_band;
    }
    return "moisture";
  }

  _moistureCheckInLabel(zone) {
    if (!zone.moisture_entity_id) return "unmapped";
    const value = zone.moisture_observed_value || zone.moisture_value;
    if (value && !["unknown", "unavailable"].includes(String(value))) {
      return zone.moisture_source_age_label || zone.moisture_age_label || "unknown";
    }
    const sourceState = String(zone.moisture_source_state || "").toLowerCase();
    const sourceAge = zone.moisture_source_age_label && zone.moisture_source_age_label !== "unknown"
      ? `entity updated ${zone.moisture_source_age_label} ago`
      : "entity update unknown";
    if (["unknown", "unavailable"].includes(sourceState)) {
      return `No valid sample (${sourceState}; ${sourceAge})`;
    }
    return "No valid sample";
  }

  _moistureValueLabel(zone) {
    const value = zone.moisture_observed_value || zone.moisture_value;
    if (!value) {
      return "No valid sample";
    }
    const age = zone.moisture_age_label && zone.moisture_age_label !== "unknown"
      ? ` \u00b7 ${zone.moisture_age_label}`
      : "";
    return `${value}%${age}`;
  }

  _moistureTitle(zone) {
    const source = zone.moisture_entity_id || "unmapped";
    const freshness = zone.moisture_freshness || "unknown";
    const confidence = zone.moisture_confidence || "none";
    const note = zone.moisture_quality_note || "ok";
    if (freshness === "expired" || note === "missing_sensor") {
      return `Moisture: no valid sample from ${source}; ${confidence} confidence; ${note}`;
    }
    return `Moisture: ${source}; ${freshness}; ${confidence} confidence; ${note}`;
  }

  _flowLabel(zone) {
    const state = zone.flow_alert_state || zone.flow_review_state || "none";
    return state === "none" ? "flow" : "alert";
  }

  _flowTone(zone) {
    const state = zone.flow_alert_state || zone.flow_review_state || "none";
    return state === "none" ? "muted" : "issue";
  }

  _supervisorTone(zone) {
    if (zone.supervisor_badge === "ok") return "ok";
    if (zone.supervisor_badge === "flow") return "issue";
    return "warn";
  }

  _escape(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  _escapeAttr(value) {
    return this._escape(value)
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
}

customElements.define("rachio-supervisor-zone-grid-card", RachioSupervisorZoneGridCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "rachio-supervisor-zone-grid-card",
  name: "Rachio Supervisor Zone Grid",
  description: "Photo-first Rachio zone grid with badges and manual Quick Run.",
});
