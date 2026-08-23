const PA_PLATFORM = "progressive_automations";

const PA_ENTITY_SUFFIXES = {
  position: "_extension",
  position_percentage: "_position_percent",
  position_calibration: "_position_calibration",
  operation_status: "_operation_status",
  target_percentage: "_target_percent",
  preset_1: "_preset_1",
  preset_2: "_preset_2",
  preset_3: "_preset_3",
  preset_4: "_preset_4",
  program_preset: "_program_preset",
  retract: "_lower_1s",
  stop: "_stop",
  extend: "_raise_1s",
  control_lock: "_control_lock",
};

const PA_LABELS = {
  position: "Extension",
  position_percentage: "Position percentage",
  position_calibration: "Position Calibration",
  operation_status: "Operation Status",
  target_percentage: "Position percentage",
  preset_1: "Preset 1",
  preset_2: "Preset 2",
  preset_3: "Preset 3",
  preset_4: "Preset 4",
  program_preset: "Program preset",
  retract: "Retract",
  stop: "Stop",
  extend: "Extend",
  control_lock: "Control lock",
};


const PA_CARD_I18N = {
  en: {
    default_name: "Bluetooth Actuator Control",
    subtitle: "Bluetooth actuator control",
    presets: "Presets",
    program_preset: "Program preset",
    position_control: "Position",
    position_percentage: "Position percentage",
    calibration_required: "Position calibration required",
    calibration_calibrating: "Position calibration in progress…",
    motion: "Motion",
    retract: "RETRACT",
    stop: "STOP",
    extend: "EXTEND",
    control_lock: "Control lock",
    locked: "Locked",
    unlocked: "Unlocked",
    locking: "Locking…",
    unlocking: "Unlocking…",
    unknown_lock: "Unknown",
    lock_action: "LOCK",
    unlock_action: "UNLOCK",
    loading: "Loading actuator controls…",
    registry_error: "Unable to read the Home Assistant entity registry.",
    ambiguous: "More than one Progressive Automations actuator control was found.",
    missing: "Missing controls"
  },
  es: {
    default_name: "Control de actuador Bluetooth",
    subtitle: "Control de actuador Bluetooth",
    presets: "Preajustes",
    program_preset: "Programar preajuste",
    position_control: "Posición",
    position_percentage: "Porcentaje de posición",
    motion: "Movimiento",
    retract: "RETRAER",
    stop: "DETENER",
    extend: "EXTENDER",
    control_lock: "Bloqueo de control",
    loading: "Cargando controles del actuador…",
    registry_error: "No se pudo leer el registro de entidades de Home Assistant.",
    ambiguous: "Se encontró más de un control de actuador de Progressive Automations.",
    missing: "Controles faltantes"
  },
  de: {
    default_name: "Bluetooth-Aktorsteuerung",
    subtitle: "Bluetooth-Aktorsteuerung",
    presets: "Voreinstellungen",
    program_preset: "Voreinstellung programmieren",
    position_control: "Position",
    position_percentage: "Position in Prozent",
    motion: "Bewegung",
    retract: "EINFAHREN",
    stop: "STOPP",
    extend: "AUSFAHREN",
    control_lock: "Bediensperre",
    loading: "Aktorsteuerung wird geladen…",
    registry_error: "Die Home-Assistant-Entitätsregistrierung konnte nicht gelesen werden.",
    ambiguous: "Es wurde mehr als eine Progressive-Automations-Aktorsteuerung gefunden.",
    missing: "Fehlende Bedienelemente"
  },
  fr: {
    default_name: "Commande d’actionneur Bluetooth",
    subtitle: "Commande d’actionneur Bluetooth",
    presets: "Préréglages",
    program_preset: "Programmer le préréglage",
    position_control: "Position",
    position_percentage: "Position en pourcentage",
    motion: "Mouvement",
    retract: "RÉTRACTER",
    stop: "ARRÊT",
    extend: "DÉPLOYER",
    control_lock: "Verrouillage des commandes",
    loading: "Chargement des commandes de l’actionneur…",
    registry_error: "Impossible de lire le registre des entités Home Assistant.",
    ambiguous: "Plusieurs commandes d’actionneur Progressive Automations ont été trouvées.",
    missing: "Commandes manquantes"
  },
  nl: {
    default_name: "Bluetooth-actuatorbesturing",
    subtitle: "Bluetooth-actuatorbesturing",
    presets: "Voorinstellingen",
    program_preset: "Voorinstelling programmeren",
    position_control: "Positie",
    position_percentage: "Positiepercentage",
    motion: "Beweging",
    retract: "INSCHUIVEN",
    stop: "STOP",
    extend: "UITSCHUIVEN",
    control_lock: "Bedieningsvergrendeling",
    loading: "Actuatorbesturing laden…",
    registry_error: "Het Home Assistant-entiteitenregister kan niet worden gelezen.",
    ambiguous: "Er is meer dan één Progressive Automations-actuatorbesturing gevonden.",
    missing: "Ontbrekende bedieningselementen"
  },
  it: {
    default_name: "Controllo attuatore Bluetooth",
    subtitle: "Controllo attuatore Bluetooth",
    presets: "Preimpostazioni",
    program_preset: "Programma preimpostazione",
    position_control: "Posizione",
    position_percentage: "Percentuale posizione",
    motion: "Movimento",
    retract: "RITIRA",
    stop: "ARRESTA",
    extend: "ESTENDI",
    control_lock: "Blocco comandi",
    loading: "Caricamento dei controlli dell’attuatore…",
    registry_error: "Impossibile leggere il registro entità di Home Assistant.",
    ambiguous: "È stato trovato più di un controllo attuatore Progressive Automations.",
    missing: "Controlli mancanti"
  },
  "pt-BR": {
    default_name: "Controle de atuador Bluetooth",
    subtitle: "Controle de atuador Bluetooth",
    presets: "Predefinições",
    program_preset: "Programar predefinição",
    position_control: "Posição",
    position_percentage: "Percentual da posição",
    motion: "Movimento",
    retract: "RECOLHER",
    stop: "PARAR",
    extend: "ESTENDER",
    control_lock: "Bloqueio dos controles",
    loading: "Carregando controles do atuador…",
    registry_error: "Não foi possível ler o registro de entidades do Home Assistant.",
    ambiguous: "Mais de um controle de atuador Progressive Automations foi encontrado.",
    missing: "Controles ausentes"
  },
  pl: {
    default_name: "Sterowanie siłownikiem Bluetooth",
    subtitle: "Sterowanie siłownikiem Bluetooth",
    presets: "Ustawienia",
    program_preset: "Programuj ustawienie",
    position_control: "Pozycja",
    position_percentage: "Procent pozycji",
    motion: "Ruch",
    retract: "WSUŃ",
    stop: "STOP",
    extend: "WYSUŃ",
    control_lock: "Blokada sterowania",
    loading: "Ładowanie sterowania siłownikiem…",
    registry_error: "Nie można odczytać rejestru encji Home Assistant.",
    ambiguous: "Znaleziono więcej niż jedno sterowanie siłownikiem Progressive Automations.",
    missing: "Brakujące elementy sterujące"
  },
  ja: {
    default_name: "Bluetoothアクチュエータ制御",
    subtitle: "Bluetoothアクチュエータ制御",
    presets: "プリセット",
    program_preset: "プリセットを登録",
    position_control: "位置",
    position_percentage: "位置（%）",
    motion: "動作",
    retract: "縮める",
    stop: "停止",
    extend: "伸ばす",
    control_lock: "操作ロック",
    loading: "アクチュエータ制御を読み込み中…",
    registry_error: "Home Assistantのエンティティレジストリを読み取れません。",
    ambiguous: "複数のProgressive Automationsアクチュエータ制御が見つかりました。",
    missing: "不足しているコントロール"
  },
  ko: {
    default_name: "Bluetooth 액추에이터 제어",
    subtitle: "Bluetooth 액추에이터 제어",
    presets: "프리셋",
    program_preset: "프리셋 설정",
    position_control: "위치",
    position_percentage: "위치 백분율",
    motion: "동작",
    retract: "수축",
    stop: "정지",
    extend: "확장",
    control_lock: "제어 잠금",
    loading: "액추에이터 제어를 불러오는 중…",
    registry_error: "Home Assistant 엔터티 레지스트리를 읽을 수 없습니다.",
    ambiguous: "Progressive Automations 액추에이터 제어가 두 개 이상 발견되었습니다.",
    missing: "누락된 제어"
  },
  "zh-Hans": {
    default_name: "蓝牙执行器控制",
    subtitle: "蓝牙执行器控制",
    presets: "预设",
    program_preset: "设置预设",
    position_control: "位置",
    position_percentage: "位置百分比",
    motion: "运动",
    retract: "缩回",
    stop: "停止",
    extend: "伸出",
    control_lock: "控制锁",
    loading: "正在加载执行器控制…",
    registry_error: "无法读取 Home Assistant 实体注册表。",
    ambiguous: "发现了多个 Progressive Automations 执行器控制。",
    missing: "缺少控制项"
  }
};

class ProgressiveAutomationsCard extends HTMLElement {
  constructor() {
    super();
    this._registry = undefined;
    this._registryPromise = undefined;
    this._resolution = undefined;
    this._registryError = undefined;
  }

  setConfig(config) {
    this.config = { ...config };
    this._resolution = undefined;
  }

  set hass(hass) {
    this._hass = hass;

    if (!this._registry && !this._registryPromise) {
      this._loadEntityRegistry();
    }

    this._render();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return {
      columns: 12,
      min_columns: 6,
    };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "name", selector: { text: {} } },
      ],
      computeLabel: (schema) =>
        schema.name === "name" ? "Card name" : undefined,
      computeHelper: (schema) =>
        schema.name === "name"
          ? "Changes only the title shown at the top of this card."
          : undefined,
    };
  }

  static getStubConfig() {
    return {};
  }

  async _loadEntityRegistry() {
    if (!this._hass || this._registryPromise) return;

    this._registryPromise = this._hass
      .callWS({ type: "config/entity_registry/list" })
      .then((entries) => {
        this._registry = entries;
        this._registryError = undefined;
        this._resolution = this._resolveFromRegistry(entries);
      })
      .catch((err) => {
        console.error(
          "Progressive Automations card: entity registry lookup failed",
          err
        );
        this._registryError = String(err);
        this._registry = [];
        this._resolution = undefined;
      })
      .finally(() => {
        this._registryPromise = undefined;
        this._render();
      });
  }

  _resolveFromRegistry(entries) {
    const integrationEntries = entries.filter(
      (entry) =>
        entry.platform === PA_PLATFORM &&
        entry.device_id &&
        entry.unique_id
    );

    const groups = new Map();
    for (const entry of integrationEntries) {
      if (!groups.has(entry.device_id)) {
        groups.set(entry.device_id, []);
      }
      groups.get(entry.device_id).push(entry);
    }

    // Hidden advanced support for multiple actuator controls:
    // an advanced YAML user may set device_id, but the visual editor intentionally
    // exposes only Card name.
    let selectedDeviceId = this.config?.device_id;
    if (selectedDeviceId && !groups.has(selectedDeviceId)) {
      selectedDeviceId = undefined;
    }

    const scored = [...groups.entries()]
      .map(([deviceId, deviceEntries]) => {
        const mapping = this._mapDeviceEntries(deviceEntries);
        const score = Object.values(mapping).filter(Boolean).length;
        return { deviceId, mapping, score };
      })
      .sort((a, b) => b.score - a.score);

    if (!selectedDeviceId) {
      if (scored.length === 1) {
        selectedDeviceId = scored[0].deviceId;
      } else if (
        scored.length > 1 &&
        scored[0].score > scored[1].score
      ) {
        selectedDeviceId = scored[0].deviceId;
      } else if (scored.length > 1) {
        return {
          deviceId: undefined,
          entities: {},
          ambiguous: true,
          deviceCount: scored.length,
        };
      }
    }

    if (!selectedDeviceId) {
      return {
        deviceId: undefined,
        entities: {},
        ambiguous: false,
        deviceCount: groups.size,
      };
    }

    return {
      deviceId: selectedDeviceId,
      entities: this._mapDeviceEntries(
        groups.get(selectedDeviceId) || []
      ),
      ambiguous: false,
      deviceCount: groups.size,
    };
  }

  _mapDeviceEntries(entries) {
    const result = {};

    for (const [field, suffix] of Object.entries(PA_ENTITY_SUFFIXES)) {
      const match = entries.find(
        (entry) => entry.unique_id.endsWith(suffix)
      );
      if (match) {
        result[field] = match.entity_id;
      }
    }

    return result;
  }

  _entities() {
    return this._resolution?.entities || {};
  }

  _state(entityId) {
    return entityId ? this._hass?.states?.[entityId] : undefined;
  }

  _callButton(entityId) {
    if (!entityId || !this._state(entityId)) return;
    this._hass.callService("button", "press", {
      entity_id: entityId,
    });
  }

  _toggleSwitch(entityId) {
    const state = this._state(entityId);
    if (!state) return;

    this._hass.callService(
      "switch",
      state.state === "on" ? "turn_off" : "turn_on",
      { entity_id: entityId }
    );
  }

  _toggleLock(entityId) {
    const state = this._state(entityId);
    if (
      !state ||
      state.state === "unavailable" ||
      state.state === "unknown" ||
      state.state === "locking" ||
      state.state === "unlocking"
    ) return;

    const shouldUnlock = state.state === "locked";
    this._hass.callService(
      "lock",
      shouldUnlock ? "unlock" : "lock",
      { entity_id: entityId }
    );
  }

  _setNumber(entityId, value) {
    const state = this._state(entityId);
    const numeric = Number(value);
    if (!state || state.state === "unavailable" || !Number.isFinite(numeric)) {
      return;
    }

    this._hass.callService("number", "set_value", {
      entity_id: entityId,
      value: numeric,
    });
  }

  _positionControl(
    entityId,
    labelKey = "position_control",
    forceDisabled = false,
    fallbackValue = undefined
  ) {
    const state = this._state(entityId);
    const unavailable = !state || state.state === "unavailable";

    const entityValue = Number.parseFloat(state?.state);
    const fallback = Number(fallbackValue);
    const displayValue = Number.isFinite(entityValue) ? entityValue : fallback;
    // Home Assistant's Number entity min/max are the currently permitted
    // *absolute physical percentages*. The custom card deliberately does not use
    // those as the visual ends of the range: the track always remains 0-100%,
    // while the allowed min/max act as hard fences within that invariant scale.
    const allowedMin = Number(state?.attributes?.allowed_min_percent ?? state?.attributes?.min);
    const allowedMax = Number(state?.attributes?.allowed_max_percent ?? state?.attributes?.max);
    const step = Number(state?.attributes?.step || 1);
    const validRange = Number.isFinite(allowedMin) && Number.isFinite(allowedMax) && allowedMax >= allowedMin;
    const disabled = forceDisabled || unavailable || !Number.isFinite(displayValue) || !validRange;

    // Keep the thumb at the live measured absolute percentage. User limits do
    // not remap the scale; they only fence where the thumb may be dragged.
    const safeValue = Number.isFinite(displayValue)
      ? Math.min(100, Math.max(0, displayValue))
      : 0;
    const safeStep = Number.isFinite(step) && step > 0 ? step : 1;
    const decimals = safeStep >= 1 ? 0 : 1;
    const rangeText = validRange
      ? `0–100% · ${allowedMin.toFixed(decimals)}–${allowedMax.toFixed(decimals)}% allowed`
      : "0–100%";

    return `
      <div class="position-control ${disabled ? "disabled" : ""}">
        <input
          type="range"
          data-position-number="${this._escape(entityId || "")}"
          min="0"
          max="100"
          step="${safeStep}"
          value="${safeValue}"
          data-current-value="${safeValue}"
          data-allowed-min="${validRange ? allowedMin : 0}"
          data-allowed-max="${validRange ? allowedMax : 100}"
          ${disabled ? "disabled" : ""}
          aria-label="${this._escape(this._t(labelKey))}"
        />
        <div class="position-range">${this._escape(rangeText)}</div>
      </div>
    `;
  }

  _escape(value) {
    // Regex replacements are intentionally used instead of String.replaceAll
    // for compatibility with older embedded WebViews used by some HA clients.
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  _button(label, entityId, extraClass = "", forceDisabled = false) {
    const state = this._state(entityId);
    const disabled = forceDisabled || !state || state.state === "unavailable";

    return `
      <button
        class="action ${extraClass}"
        data-button="${this._escape(entityId || "")}"
        ${disabled ? "disabled" : ""}
      >${this._escape(label)}</button>
    `;
  }

  _toggleRow(label, entityId, forceDisabled = false) {
    const state = this._state(entityId);
    const on = state?.state === "on";
    const disabled = forceDisabled || !state || state.state === "unavailable";

    return `
      <button
        class="toggle-row ${on ? "on" : ""}"
        data-switch="${this._escape(entityId || "")}"
        ${disabled ? "disabled" : ""}
      >
        <span>${this._escape(label)}</span>
        <span class="toggle-pill"><span class="toggle-knob"></span></span>
      </button>
    `;
  }

  _lockRow(label, entityId) {
    const state = this._state(entityId);
    const raw = state?.state || "unknown";
    const disabled =
      !state ||
      raw === "unavailable" ||
      raw === "unknown" ||
      raw === "locking" ||
      raw === "unlocking";
    const stateKey = {
      locked: "locked",
      unlocked: "unlocked",
      locking: "locking",
      unlocking: "unlocking",
    }[raw] || "unknown_lock";
    const shouldUnlock = raw === "locked";

    return `
      <div class="lock-row">
        <div>
          <div class="lock-label">${this._escape(label)}</div>
          <div class="lock-state">${this._escape(this._t(stateKey))}</div>
        </div>
        <button
          class="lock-action"
          data-lock="${this._escape(entityId || "")}"
          ${disabled ? "disabled" : ""}
        >${this._escape(this._t(shouldUnlock ? "unlock_action" : "lock_action"))}</button>
      </div>
    `;
  }

  _t(key) {
    const raw = this._hass?.language || "en";
    let lang = raw;
    if (!PA_CARD_I18N[lang]) {
      const base = raw.split("-")[0];
      lang = PA_CARD_I18N[base] ? base : "en";
    }
    return PA_CARD_I18N[lang]?.[key] ?? PA_CARD_I18N.en[key] ?? key;
  }

  _operationNotice(entities) {
    const state = this._state(entities.operation_status);
    if (!state || state.state === "unknown" || state.state === "unavailable") {
      return "";
    }

    const activityCode = state.attributes?.activity_code || "";
    if (activityCode === "idle" || state.state.toLowerCase() === "idle") {
      return "";
    }

    return `<div class="operation-status"><ha-icon icon="mdi:progress-wrench"></ha-icon><span>${this._escape(state.state)}</span></div>`;
  }

  _statusNotice(entities) {
    if (this._registryPromise && !this._registry) {
      return `<div class="notice">${this._escape(this._t("loading"))}</div>`;
    }

    if (this._registryError) {
      return `<div class="notice error">${this._escape(this._t("registry_error"))}</div>`;
    }

    if (this._resolution?.ambiguous) {
      return `<div class="notice">${this._escape(this._t("ambiguous"))}</div>`;
    }

    const missing = Object.entries(PA_ENTITY_SUFFIXES)
      .filter(([field]) => !entities[field])
      .map(([field]) => PA_LABELS[field]);

    if (missing.length) {
      return `<div class="notice">${this._escape(this._t("missing"))}: ${this._escape(
        missing.join(", ")
      )}.</div>`;
    }

    return "";
  }

  _render() {
    if (!this._hass || !this.config) return;

    const entities = this._entities();
    const position = this._state(entities.position);
    const percentage = this._state(entities.position_percentage);
    const calibration = this._state(entities.position_calibration)?.state;

    let value = "—";
    if (
      position &&
      position.state !== "unknown" &&
      position.state !== "unavailable"
    ) {
      value = this._hass.formatEntityState
        ? this._hass.formatEntityState(position)
        : `${position.state}${
            position.attributes?.unit_of_measurement
              ? " " + position.attributes.unit_of_measurement
              : ""
          }`;
    }

    let percentValue = "";
    if (
      percentage &&
      percentage.state !== "unknown" &&
      percentage.state !== "unavailable"
    ) {
      const rawPercent = Number.parseFloat(percentage.state);
      if (Number.isFinite(rawPercent)) {
        percentValue = `${Math.round(rawPercent)}%`;
      }
    }

    const headerValue = percentValue ? `${value} · ${percentValue}` : value;

    const controlLockState = this._state(entities.control_lock)?.state;
    const controlsLocked = !["unlocked"].includes(controlLockState);

    const presets = [1, 2, 3, 4]
      .map((n) =>
        this._button(
          `M${n}`,
          entities[`preset_${n}`],
          "preset",
          controlsLocked
        )
      )
      .join("");

    const title = this._escape(
      this.config.name || this._t("default_name")
    );

    this.innerHTML = `
      <ha-card>
        <div class="wrap">
          <div class="header">
            <div>
              <div class="title">${title}</div>
            </div>
            <div class="position">${this._escape(headerValue)}</div>
          </div>

          ${this._operationNotice(entities)}
          ${this._statusNotice(entities)}

          <div class="section">
            <div class="section-title">${this._escape(this._t("position_percentage"))}</div>
            ${this._positionControl(
              entities.target_percentage,
              "position_percentage",
              controlsLocked,
              Number.parseFloat(percentage?.state)
            )}
            ${calibration === "required"
              ? `<div class="calibration-note">${this._escape(this._t("calibration_required"))}</div>`
              : calibration === "calibrating"
                ? `<div class="calibration-note">${this._escape(this._t("calibration_calibrating"))}</div>`
                : ""}
          </div>

          <div class="section">
            <div class="section-title">${this._escape(this._t("presets"))}</div>
            <div class="preset-row">${presets}</div>
            ${this._toggleRow(
              this._t("program_preset"),
              entities.program_preset,
              controlsLocked
            )}
          </div>

          <div class="section">
            <div class="section-title">${this._escape(this._t("motion"))}</div>
            <div class="motion-row">
              ${this._button(
                this._t("retract"),
                entities.retract,
                "motion",
                controlsLocked
              )}
              ${this._button(
                `■ ${this._t("stop")}`,
                entities.stop,
                "stop",
                controlsLocked
              )}
              ${this._button(
                this._t("extend"),
                entities.extend,
                "motion",
                controlsLocked
              )}
            </div>
          </div>

          <div class="section compact">
            ${this._lockRow(
              this._t("control_lock"),
              entities.control_lock
            )}
          </div>
        </div>
      </ha-card>

      <style>
        :host { display: block; }
        ha-card { overflow: hidden; }
        .wrap { padding: 16px; }
        .header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 16px;
        }
        .title {
          font-size: 1.15rem;
          font-weight: 600;
          color: var(--primary-text-color);
        }
        .position {
          font-size: 1.3rem;
          font-weight: 600;
          white-space: nowrap;
          color: var(--primary-text-color);
        }
        .operation-status {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 10px 0 2px;
          padding: 9px 11px;
          border-radius: 10px;
          background: var(--secondary-background-color);
          font-size: 0.92rem;
          font-weight: 500;
        }
        .operation-status ha-icon {
          --mdc-icon-size: 18px;
          flex: 0 0 auto;
        }
        .notice {
          margin: -4px 0 12px;
          padding: 8px 10px;
          border-radius: 8px;
          background: var(--secondary-background-color);
          color: var(--secondary-text-color);
          font-size: .82rem;
        }
        .notice.error {
          color: var(--error-color);
        }
        .section {
          padding-top: 12px;
          margin-top: 12px;
          border-top: 1px solid var(--divider-color);
        }
        .section.compact {
          padding-top: 8px;
          margin-top: 8px;
        }
        .section-title {
          margin-bottom: 8px;
          font-size: .78rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: .06em;
          color: var(--secondary-text-color);
        }
        .position-control {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          align-items: center;
          gap: 12px;
        }
        .position-control.disabled {
          opacity: .45;
        }
        .position-control input[type="range"] {
          width: 100%;
          min-width: 0;
          accent-color: var(--primary-color);
          cursor: pointer;
        }
        .position-control input[type="range"]:disabled {
          cursor: not-allowed;
        }
        .position-range {
          min-width: 88px;
          text-align: right;
          white-space: nowrap;
          font-size: .78rem;
          color: var(--secondary-text-color);
        }
        .calibration-note {
          margin-top: 6px;
          font-size: .78rem;
          color: var(--secondary-text-color);
        }
        .preset-row {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 8px;
        }
        .motion-row {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 8px;
        }
        button {
          font: inherit;
          color: var(--primary-text-color);
        }
        button.action {
          min-height: 42px;
          border: 0;
          border-radius: 10px;
          padding: 8px 10px;
          background: var(--secondary-background-color);
          cursor: pointer;
        }
        button.action:hover:not(:disabled),
        button.toggle-row:hover:not(:disabled),
        button.lock-action:hover:not(:disabled) {
          filter: brightness(1.05);
        }
        button.action:active:not(:disabled) {
          transform: translateY(1px);
        }
        button.stop {
          font-weight: 700;
        }
        button:disabled {
          opacity: .4;
          cursor: not-allowed;
        }
        .lock-row {
          min-height: 48px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .lock-label {
          font-size: .95rem;
          color: var(--primary-text-color);
        }
        .lock-state {
          margin-top: 2px;
          font-size: .78rem;
          color: var(--secondary-text-color);
        }
        .lock-action {
          min-width: 84px;
          min-height: 36px;
          border: 0;
          border-radius: 10px;
          padding: 6px 12px;
          background: var(--secondary-background-color);
          font-weight: 600;
          cursor: pointer;
        }
        .toggle-row {
          width: 100%;
          min-height: 40px;
          margin-top: 8px;
          padding: 6px 2px;
          border: 0;
          background: transparent;
          display: flex;
          align-items: center;
          justify-content: space-between;
          cursor: pointer;
        }
        .toggle-pill {
          width: 38px;
          height: 22px;
          padding: 2px;
          box-sizing: border-box;
          border-radius: 999px;
          background: var(--disabled-color);
          transition: .15s ease;
        }
        .toggle-knob {
          display: block;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: var(--card-background-color);
          transform: translateX(0);
          transition: .15s ease;
        }
        .toggle-row.on .toggle-pill {
          background: var(--primary-color);
        }
        .toggle-row.on .toggle-knob {
          transform: translateX(16px);
        }
      </style>
    `;

    this.querySelectorAll("[data-button]").forEach((el) => {
      el.addEventListener("click", () =>
        this._callButton(el.dataset.button)
      );
    });

    this.querySelectorAll("[data-switch]").forEach((el) => {
      el.addEventListener("click", () =>
        this._toggleSwitch(el.dataset.switch)
      );
    });

    this.querySelectorAll("[data-lock]").forEach((el) => {
      el.addEventListener("click", () =>
        this._toggleLock(el.dataset.lock)
      );
    });

    this.querySelectorAll("[data-position-number]").forEach((el) => {
      const clampToAllowedRange = () => {
        const requested = Number(el.value);
        const allowedMin = Number(el.dataset.allowedMin);
        const allowedMax = Number(el.dataset.allowedMax);
        if (!Number.isFinite(requested)) return;
        if (Number.isFinite(allowedMin) && requested < allowedMin) {
          el.value = String(allowedMin);
        } else if (Number.isFinite(allowedMax) && requested > allowedMax) {
          el.value = String(allowedMax);
        }
      };

      // Hard-fence the thumb while it is being dragged. The visual track remains
      // the invariant 0-100 physical scale, so a 79% upper limit stays visibly
      // at 79% of the bar instead of becoming a remapped far-right endpoint.
      el.addEventListener("input", clampToAllowedRange);

      el.addEventListener("change", () => {
        clampToAllowedRange();
        const requested = el.value;
        const current = Number(el.dataset.currentValue);

        // The slider is state-driven, not optimistic. On release, snap the thumb
        // back to the last measured position; incoming FE62 position updates then
        // move it with the actual actuator.
        if (Number.isFinite(current)) {
          el.value = String(current);
        }
        this._setNumber(el.dataset.positionNumber, requested);
      });
    });
  }
}

if (!customElements.get("progressive-automations-card")) {
  customElements.define(
    "progressive-automations-card",
    ProgressiveAutomationsCard
  );
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === "progressive-automations-card")) {
  window.customCards.push({
    type: "progressive-automations-card",
    name: "Progressive Automations",
    description:
      "Compact Bluetooth actuator-control card for Progressive Automations.",
    preview: true,
  });
}
