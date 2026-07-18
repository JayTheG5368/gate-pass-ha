import { LitElement, css, html } from 'lit';
import QRCode from 'qrcode';

const COPY_CLEAR_MS = 120000;

const DURATION_OPTIONS = {
  de: [
    [0.25, '15 Minuten'], [0.5, '30 Minuten'], [1, '1 Stunde'], [2, '2 Stunden'],
    [4, '4 Stunden'], [8, '8 Stunden'], [12, '12 Stunden'], [24, '1 Tag'],
    [48, '2 Tage'], [72, '3 Tage'], [168, '1 Woche'],
  ],
  en: [
    [0.25, '15 minutes'], [0.5, '30 minutes'], [1, '1 hour'], [2, '2 hours'],
    [4, '4 hours'], [8, '8 hours'], [12, '12 hours'], [24, '1 day'],
    [48, '2 days'], [72, '3 days'], [168, '1 week'],
  ],
};

const USE_OPTIONS = {
  de: [[1, '1 Nutzung'], [2, '2 Nutzungen'], [3, '3 Nutzungen'], [5, '5 Nutzungen'], [10, '10 Nutzungen'], [0, 'Unbegrenzt']],
  en: [[1, '1 use'], [2, '2 uses'], [3, '3 uses'], [5, '5 uses'], [10, '10 uses'], [0, 'Unlimited']],
};

const TEXT = {
  de: {
    title: 'Gate Pass', active: 'Aktive Zugänge', create: 'Zugang erstellen',
    label: 'Name oder Zweck', labelPlaceholder: 'z. B. Paketdienst',
    duration: 'Gültigkeit (Stunden)', uses: 'Maximale Nutzungen',
    validFrom: 'Gültig ab', startNow: 'Sofort', startTwoHours: 'In 2 Stunden',
    startFourHours: 'In 4 Stunden', startTomorrow: 'Morgen (gleiche Uhrzeit)',
    startCustom: 'Datum und Uhrzeit wählen', customStart: 'Startzeitpunkt',
    unlimited: '0 = unbegrenzt', cancel: 'Abbrechen', submit: 'Link erstellen',
    noPasses: 'Keine aktiven Zugänge', expires: 'Läuft ab in', starts: 'Startet in', used: 'genutzt',
    revoke: 'Zugang widerrufen', revokeAll: 'Alle widerrufen', refresh: 'Aktualisieren',
    created: 'Zugang erstellt', copy: 'Link kopieren', share: 'Teilen', close: 'Schließen',
    copied: 'Link kopiert', shareFallback: 'Teilen nicht verfügbar - Link kopiert',
    qrAlt: 'QR-Code für den Gastzugang', invalidStart: 'Ungültiger Startzeitpunkt.',
    secretHint: 'Der vollständige Link wird nur jetzt angezeigt.',
    loadError: 'Gate-Pass-Daten konnten nicht geladen werden.',
    createError: 'Zugang konnte nicht erstellt werden.',
    revokeError: 'Zugang konnte nicht widerrufen werden.',
    confirmOne: 'Zugang "{label}" wirklich widerrufen?',
    confirmAll: 'Wirklich alle aktiven Zugänge widerrufen?', days: 'T', hours: 'Std', minutes: 'Min',
    cardTitle: 'Kartentitel', cardTitlePlaceholder: 'z. B. Tor-Zugänge',
    cardIcon: 'Kartensymbol', cardIconPlaceholder: 'mdi:garage-variant',
    defaultName: 'Standardname', defaultNamePlaceholder: 'Link von {user}',
    activity: 'Verlauf', noActivity: 'Noch keine Aktivitäten', clearActivity: 'Verlauf löschen',
    confirmClearActivity: 'Den gesamten Aktivitätsverlauf dauerhaft löschen?',
    clearActivityError: 'Verlauf konnte nicht gelöscht werden.',
    activityCreated: 'Zugang erstellt', activityUsed: 'Zugang verwendet',
    activityRevoked: 'Zugang widerrufen', activityUnknown: 'Aktivität',
  },
  en: {
    title: 'Gate Pass', active: 'Active passes', create: 'Create pass',
    label: 'Name or purpose', labelPlaceholder: 'e.g. parcel delivery',
    duration: 'Validity (hours)', uses: 'Maximum uses', unlimited: '0 = unlimited',
    validFrom: 'Valid from', startNow: 'Immediately', startTwoHours: 'In 2 hours',
    startFourHours: 'In 4 hours', startTomorrow: 'Tomorrow (same time)',
    startCustom: 'Choose date and time', customStart: 'Start date and time',
    cancel: 'Cancel', submit: 'Create link', noPasses: 'No active passes',
    expires: 'Expires in', starts: 'Starts in', used: 'used', revoke: 'Revoke pass', revokeAll: 'Revoke all',
    refresh: 'Refresh', created: 'Pass created', copy: 'Copy link', share: 'Share',
    close: 'Close', copied: 'Link copied', shareFallback: 'Sharing unavailable - link copied',
    qrAlt: 'QR code for guest access', invalidStart: 'Invalid start date and time.',
    secretHint: 'The complete link is only displayed now.',
    loadError: 'Gate Pass data could not be loaded.', createError: 'Pass could not be created.',
    revokeError: 'Pass could not be revoked.', confirmAll: 'Revoke all active passes?',
    confirmOne: 'Really revoke "{label}"?',
    days: 'd', hours: 'h', minutes: 'm',
    cardTitle: 'Card title', cardTitlePlaceholder: 'e.g. Gate access',
    cardIcon: 'Card icon', cardIconPlaceholder: 'mdi:garage-variant',
    defaultName: 'Default name', defaultNamePlaceholder: 'Link by {user}',
    activity: 'Activity', noActivity: 'No activity yet', clearActivity: 'Clear activity',
    confirmClearActivity: 'Permanently clear the complete activity history?',
    clearActivityError: 'Activity could not be cleared.',
    activityCreated: 'Pass created', activityUsed: 'Pass used',
    activityRevoked: 'Pass revoked', activityUnknown: 'Activity',
  },
};

class GatePassCard extends LitElement {
  static properties = {
    _hass: { state: true },
    _config: { state: true },
    _passes: { state: true },
    _activity: { state: true },
    _view: { state: true },
    _accessName: { state: true },
    _showForm: { state: true },
    _newPass: { state: true },
    _qrDataUrl: { state: true },
    _loading: { state: true },
    _error: { state: true },
    _notice: { state: true },
    _startOption: { state: true },
    _customStart: { state: true },
  };

  constructor() {
    super();
    this._passes = [];
    this._activity = [];
    this._view = 'active';
    this._accessName = '';
    this._showForm = false;
    this._newPass = null;
    this._qrDataUrl = '';
    this._loading = false;
    this._error = '';
    this._notice = '';
    this._startOption = 'now';
    this._customStart = '';
    this._draftLabel = null;
    this._eventUnsubs = [];
    this._clearTimer = null;
  }

  setConfig(config) {
    this._config = {
      title: '', icon: 'mdi:garage-variant', default_name: '',
      default_duration: 1, default_max_uses: 1, ...config,
    };
  }

  set hass(hass) {
    const firstLoad = !this._hass;
    this._hass = hass;
    if (firstLoad) {
      this._refresh();
      this._subscribe();
    }
  }

  connectedCallback() {
    super.connectedCallback();
    if (this._hass && this._eventUnsubs.length === 0) this._subscribe();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsubscribe();
    if (this._clearTimer) clearTimeout(this._clearTimer);
  }

  get _text() {
    return TEXT[this._hass?.language === 'de' ? 'de' : 'en'];
  }

  async _subscribe() {
    if (!this._hass?.connection || this._eventUnsubs.length) return;
    try {
      for (const event of ['gate_pass_created', 'gate_pass_revoked', 'gate_pass_used', 'gate_pass_activity_cleared']) {
        const unsubscribe = await this._hass.connection.subscribeEvents(() => this._refresh(), event);
        this._eventUnsubs.push(unsubscribe);
      }
    } catch (_) {
      this._unsubscribe();
    }
  }

  _unsubscribe() {
    for (const unsubscribe of this._eventUnsubs) {
      try { unsubscribe(); } catch (_) { /* no-op */ }
    }
    this._eventUnsubs = [];
  }

  async _refresh() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    try {
      const [passesResult, activityResult] = await Promise.all([
        this._hass.callWS({
          type: 'call_service', domain: 'gate_pass', service: 'list_passes', return_response: true,
        }),
        this._hass.callWS({
          type: 'call_service', domain: 'gate_pass', service: 'list_activity', return_response: true,
        }),
      ]);
      this._passes = passesResult?.response?.passes || [];
      this._activity = activityResult?.response?.activity || [];
      this._accessName = passesResult?.response?.access_name || activityResult?.response?.access_name || '';
      this._error = '';
    } catch (error) {
      this._error = `${this._text.loadError} ${error.message || ''}`.trim();
    } finally {
      this._loading = false;
    }
  }

  async _createPass(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    this._loading = true;
    this._error = '';
    try {
      const serviceData = {
        label: form.get('label') || 'Gast',
        duration_hours: Number(form.get('duration_hours')),
        max_uses: Number(form.get('max_uses')),
      };
      const validFrom = this._validFromForm(form);
      if (validFrom) serviceData.valid_from = validFrom;
      const result = await this._hass.callWS({
        type: 'call_service', domain: 'gate_pass', service: 'create_pass', return_response: true,
        service_data: serviceData,
      });
      this._newPass = result?.response || null;
      this._qrDataUrl = this._newPass?.guest_url
        ? await QRCode.toDataURL(this._newPass.guest_url, {
          width: 260, margin: 1, errorCorrectionLevel: 'M',
          color: { dark: '#111816', light: '#ffffff' },
        }) : '';
      this._showForm = false;
      this._startOption = 'now';
      this._customStart = '';
      this._draftLabel = null;
      this._scheduleClear();
      this._loading = false;
      await this._refresh();
    } catch (error) {
      this._error = `${this._text.createError} ${error.message || ''}`.trim();
    } finally {
      this._loading = false;
    }
  }

  async _revoke(passId, label) {
    if (!window.confirm(this._text.confirmOne.replace('{label}', label))) return;
    this._loading = true;
    try {
      await this._hass.callWS({
        type: 'call_service', domain: 'gate_pass', service: 'revoke_pass',
        service_data: { pass_id: passId }, return_response: true,
      });
      this._passes = this._passes.filter((item) => item.pass_id !== passId);
      this._error = '';
    } catch (error) {
      this._error = `${this._text.revokeError} ${error.message || ''}`.trim();
    } finally {
      this._loading = false;
    }
  }

  async _revokeAll() {
    if (!window.confirm(this._text.confirmAll)) return;
    this._loading = true;
    try {
      await this._hass.callWS({
        type: 'call_service', domain: 'gate_pass', service: 'revoke_all',
        return_response: true,
      });
      this._passes = [];
      this._error = '';
    } catch (error) {
      this._error = `${this._text.revokeError} ${error.message || ''}`.trim();
    } finally {
      this._loading = false;
    }
  }

  async _clearActivity() {
    if (!window.confirm(this._text.confirmClearActivity)) return;
    this._loading = true;
    try {
      await this._hass.callWS({
        type: 'call_service', domain: 'gate_pass', service: 'clear_activity',
        return_response: true,
      });
      this._activity = [];
      this._error = '';
    } catch (error) {
      this._error = `${this._text.clearActivityError} ${error.message || ''}`.trim();
    } finally {
      this._loading = false;
    }
  }

  _scheduleClear() {
    if (this._clearTimer) clearTimeout(this._clearTimer);
    this._clearTimer = setTimeout(() => this._closeResult(), COPY_CLEAR_MS);
  }

  _closeResult() {
    this._newPass = null;
    this._qrDataUrl = '';
    if (this._clearTimer) clearTimeout(this._clearTimer);
    this._clearTimer = null;
  }

  async _copy(url, notice = this._text.copied) {
    try {
      await navigator.clipboard.writeText(url);
    } catch (_) {
      const input = this.renderRoot.querySelector('.result-url');
      input?.select();
      document.execCommand('copy');
    }
    this._notice = notice;
    setTimeout(() => { this._notice = ''; }, 1800);
  }

  async _share(url) {
    const title = this._accessName || 'Gate Pass';
    const label = this._newPass?.label || title;
    const richData = { title, text: label, url };
    const textData = { title, text: `${label}\n${url}` };
    let shareData = null;
    if (navigator.share) {
      try {
        if (!navigator.canShare) shareData = textData;
        else if (navigator.canShare(richData)) shareData = richData;
        else if (navigator.canShare(textData)) shareData = textData;
      } catch (_) { /* use clipboard fallback */ }
    }
    if (shareData) {
      try {
        await navigator.share(shareData);
        return;
      } catch (error) {
        if (error?.name === 'AbortError') return;
      }
    }
    await this._copy(url, this._text.shareFallback);
  }

  _validFromForm(form) {
    const option = String(form.get('start_option') || 'now');
    if (option === 'now') return null;
    const start = new Date();
    if (option === 'two_hours') start.setTime(start.getTime() + 2 * 60 * 60 * 1000);
    else if (option === 'four_hours') start.setTime(start.getTime() + 4 * 60 * 60 * 1000);
    else if (option === 'tomorrow') start.setDate(start.getDate() + 1);
    else if (option === 'custom') {
      const custom = new Date(String(form.get('valid_from') || ''));
      if (Number.isNaN(custom.getTime())) throw new Error(this._text.invalidStart);
      return custom.toISOString();
    } else {
      throw new Error(this._text.invalidStart);
    }
    return start.toISOString();
  }

  _startOptionChanged(event) {
    this._startOption = event.currentTarget.value;
    if (this._startOption === 'custom' && !this._customStart) {
      const start = new Date(Date.now() + 2 * 60 * 60 * 1000);
      start.setMinutes(0, 0, 0);
      this._customStart = this._localDateTimeValue(start);
    }
  }

  _localDateTimeValue(date) {
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }

  _defaultLabel() {
    const user = String(this._hass?.user?.name || '').trim();
    const template = String(this._config?.default_name || '').trim();
    if (template) {
      const value = template.replaceAll('{user}', user).trim();
      return value.slice(0, 80);
    }
    if (!user) return '';
    const prefix = this._hass?.language === 'de' ? 'Link von' : 'Link by';
    return `${prefix} ${user}`.slice(0, 80);
  }

  _toggleForm() {
    this._view = 'active';
    this._showForm = !this._showForm;
    if (this._showForm) this._draftLabel = this._defaultLabel();
    else this._draftLabel = null;
  }

  _cancelForm() {
    this._showForm = false;
    this._startOption = 'now';
    this._customStart = '';
    this._draftLabel = null;
  }

  _remaining(iso) {
    const milliseconds = Math.max(0, new Date(iso).getTime() - Date.now());
    const minutes = Math.floor(milliseconds / 60000);
    const days = Math.floor(minutes / 1440);
    const hours = Math.floor((minutes % 1440) / 60);
    if (days) return `${days}${this._text.days} ${hours}${this._text.hours}`;
    if (hours) return `${hours}${this._text.hours} ${minutes % 60}${this._text.minutes}`;
    return `${minutes}${this._text.minutes}`;
  }

  render() {
    const t = this._text;
    return html`
      <ha-card>
        <header>
          <div class="title-block"><ha-icon icon=${this._config?.icon || 'mdi:garage-variant'}></ha-icon><div><h2>${this._config?.title || this._accessName || t.title}</h2>${this._config?.title && this._accessName ? html`<p>${this._accessName}</p>` : ''}</div></div>
          <div class="header-actions">
            <ha-icon-button title=${t.refresh} @click=${this._refresh} .disabled=${this._loading}><ha-icon icon="mdi:refresh"></ha-icon></ha-icon-button>
            <ha-button appearance="accent" @click=${this._toggleForm}><ha-icon icon="mdi:plus" slot="start"></ha-icon>${t.create}</ha-button>
          </div>
        </header>

        ${this._error ? html`<div class="banner error">${this._error}</div>` : ''}
        ${this._notice ? html`<div class="banner notice">${this._notice}</div>` : ''}
        ${this._showForm ? this._renderForm(t) : ''}
        ${this._newPass ? this._renderResult(t) : ''}

        <nav class="tabs" aria-label=${t.title}>
          <button type="button" class=${this._view === 'active' ? 'tab active' : 'tab'} aria-pressed=${this._view === 'active'} @click=${() => { this._view = 'active'; }}>
            <ha-icon icon="mdi:ticket-confirmation-outline"></ha-icon><span>${t.active}</span><strong>${this._passes.length}</strong>
          </button>
          <button type="button" class=${this._view === 'activity' ? 'tab active' : 'tab'} aria-pressed=${this._view === 'activity'} @click=${() => { this._view = 'activity'; }}>
            <ha-icon icon="mdi:history"></ha-icon><span>${t.activity}</span><strong>${this._activity.length}</strong>
          </button>
        </nav>

        ${this._view === 'active' ? html`
          <section>
            <div class="section-heading"><h3>${t.active}</h3>${this._passes.length ? html`<ha-button class="danger" @click=${this._revokeAll}>${t.revokeAll}</ha-button>` : ''}</div>
            ${this._passes.length ? this._passes.map((pass) => this._renderPass(pass, t)) : html`<div class="empty"><ha-icon icon="mdi:ticket-outline"></ha-icon><span>${t.noPasses}</span></div>`}
          </section>
        ` : html`
          <section>
            <div class="section-heading"><h3>${t.activity}</h3>${this._activity.length ? html`<ha-button class="danger" @click=${this._clearActivity}>${t.clearActivity}</ha-button>` : ''}</div>
            ${this._activity.length ? this._activity.map((item) => this._renderActivity(item, t)) : html`<div class="empty"><ha-icon icon="mdi:history"></ha-icon><span>${t.noActivity}</span></div>`}
          </section>
        `}
      </ha-card>
    `;
  }

  _renderForm(t) {
    const language = this._hass?.language === 'de' ? 'de' : 'en';
    const durationValue = Number(this._config.default_duration);
    const usesValue = Number(this._config.default_max_uses);
    const configuredDuration = Number.isFinite(durationValue) && durationValue >= 0.1 && durationValue <= 720
      ? durationValue : 1;
    const configuredUses = Number.isInteger(usesValue) && usesValue >= 0 && usesValue <= 1000
      ? usesValue : 1;
    const durations = [...DURATION_OPTIONS[language]];
    const uses = [...USE_OPTIONS[language]];
    if (!durations.some(([value]) => value === configuredDuration)) {
      durations.push([configuredDuration, `${configuredDuration} h`]);
      durations.sort(([left], [right]) => left - right);
    }
    if (!uses.some(([value]) => value === configuredUses)) {
      uses.splice(uses.length - 1, 0, [configuredUses, String(configuredUses)]);
    }
    const startOptions = [
      ['now', t.startNow], ['two_hours', t.startTwoHours],
      ['four_hours', t.startFourHours], ['tomorrow', t.startTomorrow],
      ['custom', t.startCustom],
    ];
    return html`
      <form @submit=${this._createPass}>
        <label><span>${t.label}</span><input name="label" maxlength="80" .value=${this._draftLabel ?? this._defaultLabel()} @input=${(event) => { this._draftLabel = event.currentTarget.value; }} placeholder=${t.labelPlaceholder} required></label>
        <div class="form-grid">
          <label><span>${t.duration}</span><select name="duration_hours" required>${durations.map(([value, label]) => html`<option value=${String(value)} ?selected=${value === configuredDuration}>${label}</option>`)}</select></label>
          <label><span>${t.uses}</span><select name="max_uses" aria-description=${t.unlimited} required>${uses.map(([value, label]) => html`<option value=${String(value)} ?selected=${value === configuredUses}>${label}</option>`)}</select></label>
          <label class="full-width"><span>${t.validFrom}</span><select name="start_option" @change=${this._startOptionChanged} required>${startOptions.map(([value, label]) => html`<option value=${value} ?selected=${value === this._startOption}>${label}</option>`)}</select></label>
          ${this._startOption === 'custom' ? html`<label class="full-width"><span>${t.customStart}</span><input name="valid_from" type="datetime-local" min=${this._localDateTimeValue(new Date())} .value=${this._customStart} @change=${(event) => { this._customStart = event.currentTarget.value; }} required></label>` : ''}
        </div>
        <div class="form-actions"><ha-button variant="neutral" appearance="filled" type="button" @click=${this._cancelForm}>${t.cancel}</ha-button><ha-button appearance="accent" type="submit" .disabled=${this._loading}>${t.submit}</ha-button></div>
      </form>
    `;
  }

  _renderResult(t) {
    const scheduled = this._newPass.valid_from
      && new Date(this._newPass.valid_from).getTime() > Date.now() + 60000;
    return html`
      <section class="result">
        <div class="result-heading"><h3>${t.created}</h3><ha-icon-button title=${t.close} @click=${this._closeResult}><ha-icon icon="mdi:close"></ha-icon></ha-icon-button></div>
        ${this._qrDataUrl ? html`<img src=${this._qrDataUrl} alt=${t.qrAlt}>` : ''}
        ${scheduled ? html`<p class="result-start"><ha-icon icon="mdi:clock-outline"></ha-icon>${t.validFrom}: ${new Date(this._newPass.valid_from).toLocaleString()}</p>` : ''}
        <p class="secret-hint">${t.secretHint}</p>
        <input class="result-url" .value=${this._newPass.guest_url || ''} readonly>
        <div class="result-actions"><ha-button appearance="accent" @click=${() => this._copy(this._newPass.guest_url)}><ha-icon icon="mdi:content-copy" slot="start"></ha-icon>${t.copy}</ha-button><ha-button variant="neutral" appearance="filled" @click=${() => this._share(this._newPass.guest_url)}><ha-icon icon="mdi:share-variant" slot="start"></ha-icon>${t.share}</ha-button></div>
      </section>
    `;
  }

  _renderPass(pass, t) {
    const limit = pass.max_uses === 0 ? '∞' : `${pass.use_count}/${pass.max_uses}`;
    const scheduled = pass.valid_from && new Date(pass.valid_from).getTime() > Date.now();
    const timing = scheduled
      ? `${t.starts} ${this._remaining(pass.valid_from)}`
      : `${t.expires} ${this._remaining(pass.expires_at)}`;
    return html`
      <div class="pass-row">
        <div class="pass-icon"><ha-icon icon="mdi:ticket-confirmation-outline"></ha-icon></div>
        <div class="pass-info"><strong>${pass.label}</strong><span>${timing} · ${limit} ${t.used}</span></div>
        <ha-icon-button title=${t.revoke} @click=${() => this._revoke(pass.pass_id, pass.label)} .disabled=${this._loading}><ha-icon icon="mdi:delete-outline"></ha-icon></ha-icon-button>
      </div>
    `;
  }

  _renderActivity(item, t) {
    const eventLabels = {
      created: t.activityCreated,
      used: t.activityUsed,
      revoked: t.activityRevoked,
    };
    const eventIcons = {
      created: 'mdi:ticket-plus-outline',
      used: 'mdi:door-open',
      revoked: 'mdi:ticket-remove-outline',
    };
    const occurredAt = new Date(item.occurred_at);
    const time = Number.isNaN(occurredAt.getTime()) ? '' : occurredAt.toLocaleString();
    return html`
      <div class="activity-row">
        <div class="pass-icon"><ha-icon icon=${eventIcons[item.event_type] || 'mdi:history'}></ha-icon></div>
        <div class="pass-info"><strong>${item.label}</strong><span>${eventLabels[item.event_type] || t.activityUnknown}${time ? ` · ${time}` : ''}</span></div>
      </div>
    `;
  }

  getCardSize() {
    const visibleRows = this._view === 'activity' ? this._activity.length : this._passes.length;
    return 3 + Math.max(1, visibleRows) + (this._newPass ? 4 : 0) + (this._showForm ? 3 : 0);
  }

  static getConfigElement() { return document.createElement('gate-pass-card-editor'); }

  static getStubConfig() {
    return {
      title: '', icon: 'mdi:garage-variant', default_name: '',
      default_duration: 1, default_max_uses: 1,
    };
  }

  static styles = css`
    :host { display:block; min-width:0; }
    *, *::before, *::after { box-sizing:border-box; }
    ha-card { padding:16px; color:var(--primary-text-color); min-width:0; }
    header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding-bottom:14px; border-bottom:1px solid var(--divider-color); }
    .title-block, .header-actions, .section-heading, .result-heading, .result-actions, .form-actions { display:flex; align-items:center; }
    .title-block { gap:10px; min-width:0; } .title-block > ha-icon { color:var(--primary-color); --mdc-icon-size:28px; }
    h2, h3, p { margin:0; } h2 { font-size:1.15rem; } h3 { font-size:.95rem; }
    .title-block p { color:var(--secondary-text-color); font-size:.78rem; margin-top:2px; }
    .header-actions { gap:6px; flex-wrap:wrap; justify-content:flex-end; }
    .tabs { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); margin-top:14px; border-bottom:1px solid var(--divider-color); }
    .tab { min-width:0; min-height:44px; display:flex; align-items:center; justify-content:center; gap:7px; padding:8px 10px; border:0; border-bottom:3px solid transparent; background:transparent; color:var(--secondary-text-color); font:inherit; font-size:.82rem; font-weight:600; line-height:1.2; cursor:pointer; letter-spacing:0; }
    .tab.active { color:var(--primary-color); border-bottom-color:var(--primary-color); }
    .tab ha-icon { --mdc-icon-size:19px; flex:0 0 auto; }
    .tab span { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .tab strong { min-width:22px; height:22px; display:inline-grid; place-items:center; padding:0 6px; border-radius:8px; background:var(--secondary-background-color); color:var(--primary-text-color); font-size:.72rem; }
    section { padding-top:16px; } .section-heading { justify-content:space-between; margin-bottom:8px; }
    form, .result { margin-top:14px; padding:14px 0 16px; border-bottom:1px solid var(--divider-color); }
    label { display:block; min-width:0; } label span { display:block; color:var(--secondary-text-color); font-size:.78rem; margin-bottom:5px; }
    input, select { display:block; width:100%; min-width:0; height:44px; padding:8px 10px; border:1px solid var(--divider-color); border-radius:6px; background:var(--card-background-color); color:var(--primary-text-color); font:inherit; letter-spacing:0; }
    select { cursor:pointer; }
    .form-grid { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:10px; margin-top:10px; min-width:0; }
    .full-width { grid-column:1 / -1; }
    .form-actions, .result-actions { justify-content:flex-end; gap:8px; margin-top:12px; }
    .pass-row { display:grid; grid-template-columns:38px minmax(0,1fr) 44px; align-items:center; gap:8px; min-height:58px; border-bottom:1px solid var(--divider-color); }
    .activity-row { display:grid; grid-template-columns:38px minmax(0,1fr); align-items:center; gap:8px; min-height:58px; border-bottom:1px solid var(--divider-color); }
    .activity-row:last-child { border-bottom:0; }
    .pass-row:last-child { border-bottom:0; } .pass-icon { width:34px; height:34px; display:grid; place-items:center; border-radius:6px; background:var(--secondary-background-color); color:var(--primary-color); }
    .pass-info { min-width:0; } .pass-info strong, .pass-info span { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .pass-info strong { font-size:.9rem; } .pass-info span { color:var(--secondary-text-color); font-size:.76rem; margin-top:3px; }
    .empty { min-height:90px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; color:var(--secondary-text-color); }
    .empty ha-icon { --mdc-icon-size:28px; }
    .result { text-align:center; } .result-heading { justify-content:space-between; } .result img { width:220px; height:220px; max-width:100%; margin:12px auto; display:block; background:#fff; padding:6px; border:1px solid var(--divider-color); border-radius:6px; }
    .secret-hint { color:var(--secondary-text-color); font-size:.78rem; margin-bottom:8px; }
    .result-start { display:flex; align-items:center; justify-content:center; gap:6px; color:var(--primary-text-color); font-size:.82rem; margin-bottom:8px; }
    .result-start ha-icon { --mdc-icon-size:18px; color:var(--primary-color); }
    .result-url { font-size:.76rem; }
    .banner { margin-top:12px; padding:9px 11px; border-radius:6px; font-size:.82rem; } .banner.error { background:var(--error-color); color:#fff; } .banner.notice { background:var(--success-color,#2e7d32); color:#fff; }
    .danger { color:var(--error-color); }
    @media (max-width:520px) {
      header { align-items:stretch; flex-direction:column; }
      .header-actions { width:100%; justify-content:space-between; flex-wrap:nowrap; }
      .header-actions ha-button { flex:1; }
      .form-grid { grid-template-columns:minmax(0,1fr); }
      .form-actions, .result-actions { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); }
      .form-actions ha-button, .result-actions ha-button { width:100%; }
    }
    @media (max-width:380px) {
      .tab { min-height:52px; gap:4px; padding-inline:4px; }
      .tab span { white-space:normal; line-height:1.1; }
    }
  `;
}

class GatePassCardEditor extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { state: true },
  };

  setConfig(config) {
    this._config = { ...config };
  }

  _valueChanged(event) {
    const config = { ...this._config };
    const key = event.currentTarget.dataset.configKey;
    const value = event.currentTarget.value.trim();
    if (value) config[key] = value;
    else delete config[key];
    this._config = config;
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config }, bubbles: true, composed: true,
    }));
  }

  render() {
    if (!this._config) return html``;
    const t = TEXT[this.hass?.language === 'de' ? 'de' : 'en'];
    return html`
      <div class="editor-grid">
        <label>
          <span>${t.cardTitle}</span>
          <input data-config-key="title" .value=${this._config.title || ''} placeholder=${t.cardTitlePlaceholder} @change=${this._valueChanged}>
        </label>
        <label>
          <span>${t.cardIcon}</span>
          <div class="icon-input"><ha-icon icon=${this._config.icon || 'mdi:garage-variant'}></ha-icon><input data-config-key="icon" .value=${this._config.icon || ''} placeholder=${t.cardIconPlaceholder} @change=${this._valueChanged}></div>
        </label>
        <label>
          <span>${t.defaultName}</span>
          <input data-config-key="default_name" maxlength="80" .value=${this._config.default_name || ''} placeholder=${t.defaultNamePlaceholder} @change=${this._valueChanged}>
        </label>
      </div>
    `;
  }

  static styles = css`
    :host { display:block; padding:8px 0; }
    *, *::before, *::after { box-sizing:border-box; }
    .editor-grid { display:grid; gap:12px; }
    label, label span, input { display:block; width:100%; }
    label span { color:var(--secondary-text-color); font-size:.875rem; margin-bottom:6px; }
    input { min-width:0; height:44px; padding:8px 10px; border:1px solid var(--divider-color); border-radius:6px; background:var(--card-background-color); color:var(--primary-text-color); font:inherit; letter-spacing:0; }
    .icon-input { display:grid; grid-template-columns:44px minmax(0,1fr); align-items:center; }
    .icon-input ha-icon { width:44px; color:var(--primary-color); }
    .icon-input input { border-start-start-radius:0; border-end-start-radius:0; }
  `;
}

if (!customElements.get('gate-pass-card-editor')) customElements.define('gate-pass-card-editor', GatePassCardEditor);
if (!customElements.get('gate-pass-card')) customElements.define('gate-pass-card', GatePassCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'gate-pass-card', name: 'Gate Pass', description: 'Temporary access links for one fixed Home Assistant action', preview: false,
});
