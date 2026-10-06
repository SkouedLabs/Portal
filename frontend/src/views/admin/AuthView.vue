<template>
  <div>
    <div class="page-title">
      <h1>Authentication</h1>
      <p>Directory connectors and session options. Secrets are encrypted in the database (AES-256-GCM) and are never sent back to the browser.</p>
    </div>

    <div class="tabs">
      <button :class="{ active: tab === 'ldap' }" @click="tab = 'ldap'"><i class="fa-solid fa-sitemap"></i> LDAP / Active Directory</button>
      <button :class="{ active: tab === 'oidc' }" @click="tab = 'oidc'"><i class="fa-solid fa-id-badge"></i> OpenID Connect</button>
      <button :class="{ active: tab === 'mfa' }" @click="tab = 'mfa'"><i class="fa-solid fa-shield-halved"></i> Two-step verification</button>
      <button :class="{ active: tab === 'general' }" @click="tab = 'general'"><i class="fa-solid fa-gear"></i> Local sign-in &amp; sessions</button>
    </div>

    <!-- LDAP -->
    <div v-if="tab === 'ldap' && ldap" class="card-ui">
      <div class="head">
        <label class="switch"><input v-model="ldap.enabled" type="checkbox" /><span class="track"></span> <strong>Enable LDAP</strong></label>
        <div style="flex: 1"></div>
        <select class="input sm" style="width: auto" @change="preset($event.target.value); $event.target.value = ''">
          <option value="">Preset…</option>
          <option value="openldap">OpenLDAP</option>
          <option value="ad">Active Directory</option>
          <option value="freeipa">FreeIPA</option>
        </select>
      </div>

      <h3 class="sub">Connection</h3>
      <div class="row">
        <div class="field" style="flex: 2 1 300px">
          <label>Server URI</label>
          <input v-model="ldap.server_uri" class="input mono" placeholder="ldaps://ldap.example.com:636" />
        </div>
        <div class="field opts">
          <label class="check"><input v-model="ldap.start_tls" type="checkbox" /> StartTLS (ldap://)</label>
          <label class="check"><input v-model="ldap.verify_tls" type="checkbox" /> Verify certificate</label>
        </div>
      </div>
      <div v-if="ldap.server_uri.startsWith('ldap://') && !ldap.start_tls" class="alert error">
        Plaintext LDAP connection: passwords would travel unencrypted. Use ldaps:// or StartTLS.
      </div>
      <div class="field">
        <label>CA certificate (PEM, optional)</label>
        <textarea v-model="ldap.ca_cert" class="input mono" rows="3" placeholder="-----BEGIN CERTIFICATE-----"></textarea>
      </div>
      <div class="row">
        <div class="field"><label>Service DN (bind)</label><input v-model="ldap.bind_dn" class="input mono" placeholder="cn=portal,ou=services,dc=example,dc=com" /></div>
        <div class="field">
          <label>Service password</label>
          <input v-model="ldapPassword" class="input" type="password" autocomplete="new-password" :placeholder="ldap.bind_password_set ? '•••••••• (unchanged)' : ''" />
        </div>
      </div>

      <h3 class="sub">Users</h3>
      <div class="row">
        <div class="field"><label>Users base DN</label><input v-model="ldap.user_base_dn" class="input mono" placeholder="ou=people,dc=example,dc=com" /></div>
        <div class="field">
          <label>User filter</label>
          <input v-model="ldap.user_filter" class="input mono" />
          <span class="hint"><code>{username}</code> is replaced by the typed username (escaped).</span>
        </div>
      </div>
      <div class="row">
        <div class="field"><label>Username attribute</label><input v-model="ldap.attr_username" class="input mono" /></div>
        <div class="field"><label>Email attribute</label><input v-model="ldap.attr_email" class="input mono" /></div>
        <div class="field"><label>Display name attribute</label><input v-model="ldap.attr_display_name" class="input mono" /></div>
      </div>

      <h3 class="sub">Groups</h3>
      <div class="row">
        <div class="field"><label>Groups base DN</label><input v-model="ldap.group_base_dn" class="input mono" placeholder="ou=groups,dc=example,dc=com" /></div>
        <div class="field"><label>Group filter</label><input v-model="ldap.group_filter" class="input mono" /></div>
      </div>
      <div class="row">
        <div class="field"><label>Member attribute</label><input v-model="ldap.group_member_attr" class="input mono" /></div>
        <div class="field"><label>Group name attribute</label><input v-model="ldap.group_name_attr" class="input mono" /></div>
        <div class="field opts">
          <label class="check"><input v-model="ldap.group_member_uses_dn" type="checkbox" /> Member is a DN</label>
          <span class="hint">Untick for posixGroup / memberUid.</span>
        </div>
      </div>

      <div v-if="ldapResult" class="alert" :class="ldapResult.ok ? 'ok' : 'error'">
        <template v-if="ldapResult.ok">Connection successful — {{ ldapResult.users_found }} user(s) and {{ ldapResult.groups_found }} group(s) found.</template>
        <template v-else>{{ ldapResult.error }}</template>
      </div>
      <div class="actions-row">
        <button class="btn" :disabled="busy" @click="testLdap"><i class="fa-solid fa-plug"></i> Save and test</button>
        <button class="btn" :disabled="busy || !ldap.enabled" @click="syncLdap"><i class="fa-solid fa-arrows-rotate"></i> Synchronise groups</button>
        <button class="btn primary" :disabled="busy" @click="saveLdap"><i class="fa-solid fa-floppy-disk"></i> Save</button>
      </div>
    </div>

    <!-- OIDC -->
    <div v-if="tab === 'oidc' && oidc" class="card-ui">
      <label class="switch"><input v-model="oidc.enabled" type="checkbox" /><span class="track"></span> <strong>Enable OpenID Connect</strong></label>

      <div class="alert info" style="margin-top: 16px">
        Redirect URI to register with the provider:
        <code class="copy" @click="copy(redirectUri)">{{ redirectUri }}</code>
        <i class="fa-regular fa-copy"></i>
      </div>

      <div class="field">
        <label>Issuer</label>
        <input v-model="oidc.issuer" class="input mono" placeholder="https://sso.example.com/realms/entreprise" />
        <span class="hint">Configuration is discovered via /.well-known/openid-configuration.</span>
      </div>
      <div class="row">
        <div class="field"><label>Client ID</label><input v-model="oidc.client_id" class="input mono" /></div>
        <div class="field">
          <label>Client secret</label>
          <input v-model="oidcSecret" class="input" type="password" autocomplete="new-password" :placeholder="oidc.client_secret_set ? '•••••••• (unchanged)' : ''" />
        </div>
        <div class="field">
          <label>Client authentication</label>
          <select v-model="oidc.token_auth_method" class="input">
            <option value="client_secret_basic">client_secret_basic</option>
            <option value="client_secret_post">client_secret_post</option>
          </select>
        </div>
      </div>
      <div class="row">
        <div class="field"><label>Scopes</label><input v-model="oidc.scopes" class="input mono" /></div>
        <div class="field">
          <label>Groups claim</label>
          <input v-model="oidc.groups_claim" class="input mono" />
          <span class="hint">Dotted paths are accepted, e.g. <code>realm_access.roles</code>.</span>
        </div>
        <div class="field"><label>Username claim</label><input v-model="oidc.username_claim" class="input mono" /></div>
      </div>
      <div class="row">
        <div class="field"><label>Button label</label><input v-model="oidc.button_label" class="input" /></div>
        <div class="field opts">
          <label class="check"><input v-model="oidc.verify_tls" type="checkbox" /> Verify TLS certificate</label>
          <label class="check"><input v-model="oidc.auto_redirect" type="checkbox" /> Redirect to SSO automatically</label>
          <span class="hint">Break-glass access to the local form: /login?local=1</span>
        </div>
      </div>

      <div v-if="oidcResult" class="alert" :class="oidcResult.ok ? 'ok' : 'error'">
        <template v-if="oidcResult.ok">
          Provider reachable: {{ oidcResult.issuer }}<br />
          Signing algorithms: {{ (oidcResult.algs || []).join(', ') || 'n/a' }}
        </template>
        <template v-else>{{ oidcResult.error }}</template>
      </div>
      <div class="actions-row">
        <button class="btn" :disabled="busy" @click="testOidc"><i class="fa-solid fa-plug"></i> Save and test</button>
        <button class="btn primary" :disabled="busy" @click="saveOidc"><i class="fa-solid fa-floppy-disk"></i> Save</button>
      </div>
    </div>

    <!-- Two-step verification -->
    <div v-if="tab === 'mfa' && mfa" class="card-ui">
      <p class="muted" style="margin-top: 0">
        Applies to local and LDAP accounts. Accounts signing in with OpenID Connect use the MFA of their identity provider.
      </p>
      <label class="switch"><input v-model="mfa.totp_enabled" type="checkbox" /><span class="track"></span> Authenticator apps (TOTP)</label>
      <br />
      <label class="switch" style="margin-top: 10px"><input v-model="mfa.webauthn_enabled" type="checkbox" /><span class="track"></span> Security keys and passkeys (WebAuthn)</label>
      <div class="field" style="max-width: 420px; margin-top: 16px">
        <label>Require two-step verification for</label>
        <select v-model="mfa.enforce" class="input">
          <option value="off">Nobody (optional, users opt in from their Security page)</option>
          <option value="admins">Administrators</option>
          <option value="all">Every local and LDAP account</option>
        </select>
        <span class="hint">Users without a second factor are asked to set one up at their next sign-in.</span>
      </div>
      <div class="alert info">
        WebAuthn is bound to the portal address: <code>PUBLIC_URL</code> must match the URL users type in their browser.
        Admins can reset a user's methods from the Users page.
      </div>
      <div class="actions-row">
        <button class="btn primary" @click="saveMfa"><i class="fa-solid fa-floppy-disk"></i> Save</button>
      </div>
    </div>

    <!-- Local sign-in & sessions -->
    <div v-if="tab === 'general' && auth" class="card-ui">
      <div v-if="auth.local_login_state.forced_by_env" class="alert info">
        <i class="fa-solid fa-lock-open"></i> Local sign-in is forced on by the <code>FORCE_LOCAL_LOGIN</code> environment variable.
        Remove it from the compose file once access is restored.
      </div>
      <label class="switch" :title="auth.local_login_state.external_enabled ? '' : 'Enable LDAP or OpenID Connect first'">
        <input v-model="auth.local_login_enabled" type="checkbox" :disabled="!auth.local_login_state.external_enabled && auth.local_login_enabled" />
        <span class="track"></span> Allow local accounts to sign in
      </label>
      <p class="hint muted">
        Can only be turned off while LDAP or OpenID Connect is enabled. To get local sign-in back (for example if the directory is down),
        set <code>FORCE_LOCAL_LOGIN=true</code> on the backend in docker-compose.yml and restart it.
      </p>
      <div v-if="!auth.local_login_enabled && !auth.local_login_state.forced_by_env" class="alert error">
        Local accounts, including the super-admin, cannot sign in. Make sure an LDAP or OIDC group is flagged as administrator.
      </div>
      <div class="field" style="max-width: 260px">
        <label>Session lifetime (hours)</label>
        <input v-model.number="auth.session_ttl_hours" type="number" min="1" max="720" class="input" />
      </div>
      <div class="actions-row">
        <button class="btn primary" @click="saveAuth"><i class="fa-solid fa-floppy-disk"></i> Save</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { api } from '../../api'
import { loadPublicConfig, notify } from '../../store'

const tab = ref('ldap')
const mfa = ref(null)
const ldap = ref(null)
const oidc = ref(null)
const auth = ref(null)
const ldapPassword = ref('')
const oidcSecret = ref('')
const ldapResult = ref(null)
const oidcResult = ref(null)
const redirectUri = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    ;[ldap.value, oidc.value, auth.value, mfa.value, { redirect_uri: redirectUri.value }] = await Promise.all([
      api.get('/api/admin/settings/ldap'),
      api.get('/api/admin/settings/oidc'),
      api.get('/api/admin/settings/auth'),
      api.get('/api/admin/settings/mfa'),
      api.get('/api/admin/oidc/redirect-uri'),
    ])
  } catch (e) {
    notify(e.message, 'error')
  }
})

// Whether local sign-in can be disabled depends on LDAP / OIDC: refresh when opening the tab.
watch(tab, async (t) => {
  if (t === 'general') auth.value = await api.get('/api/admin/settings/auth').catch(() => auth.value)
})

async function saveMfa() {
  try {
    mfa.value = await api.put('/api/admin/settings/mfa', mfa.value)
    notify('Two-step verification settings saved')
  } catch (e) {
    notify(e.message, 'error')
  }
}

const PRESETS = {
  openldap: {
    user_filter: '(&(objectClass=inetOrgPerson)(uid={username}))', attr_username: 'uid', attr_email: 'mail', attr_display_name: 'cn',
    group_filter: '(|(objectClass=groupOfNames)(objectClass=groupOfUniqueNames))', group_member_attr: 'member', group_name_attr: 'cn', group_member_uses_dn: true,
  },
  ad: {
    user_filter: '(&(objectCategory=person)(objectClass=user)(sAMAccountName={username})(!(userAccountControl:1.2.840.113556.1.4.803:=2)))',
    attr_username: 'sAMAccountName', attr_email: 'mail', attr_display_name: 'displayName',
    group_filter: '(objectClass=group)', group_member_attr: 'member', group_name_attr: 'cn', group_member_uses_dn: true,
  },
  freeipa: {
    user_filter: '(&(objectClass=person)(uid={username}))', attr_username: 'uid', attr_email: 'mail', attr_display_name: 'displayName',
    group_filter: '(objectClass=groupOfNames)', group_member_attr: 'member', group_name_attr: 'cn', group_member_uses_dn: true,
  },
}
function preset(name) {
  if (PRESETS[name]) Object.assign(ldap.value, PRESETS[name])
}

async function persist(section, data, secretField, secretRef) {
  const payload = { ...data }
  delete payload[`${secretField}_set`]
  payload[secretField] = secretRef.value ? secretRef.value : null
  const saved = await api.put(`/api/admin/settings/${section}`, payload)
  secretRef.value = ''
  await loadPublicConfig()
  return saved
}

async function saveLdap() {
  busy.value = true
  try {
    ldap.value = await persist('ldap', ldap.value, 'bind_password', ldapPassword)
    notify('LDAP configuration saved')
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
async function testLdap() {
  await saveLdap()
  busy.value = true
  ldapResult.value = null
  try {
    ldapResult.value = await api.post('/api/admin/ldap/test')
  } catch (e) {
    ldapResult.value = { ok: false, error: e.message }
  } finally {
    busy.value = false
  }
}
async function syncLdap() {
  busy.value = true
  try {
    const r = await api.post('/api/admin/ldap/sync')
    notify(`${r.groups} group(s) synchronised, ${r.users_updated} user(s) updated`)
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
async function saveOidc() {
  busy.value = true
  try {
    oidc.value = await persist('oidc', oidc.value, 'client_secret', oidcSecret)
    notify('OIDC configuration saved')
  } catch (e) {
    notify(e.message, 'error')
  } finally {
    busy.value = false
  }
}
async function testOidc() {
  await saveOidc()
  busy.value = true
  oidcResult.value = null
  try {
    oidcResult.value = await api.post('/api/admin/oidc/test')
  } catch (e) {
    oidcResult.value = { ok: false, error: e.message }
  } finally {
    busy.value = false
  }
}
async function saveAuth() {
  try {
    auth.value = await api.put('/api/admin/settings/auth', auth.value)
    await loadPublicConfig()
    notify('Settings saved')
  } catch (e) {
    notify(e.message, 'error')
  }
}
function copy(text) {
  navigator.clipboard?.writeText(text).then(() => notify('Copied'))
}
</script>

<style scoped>
.head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.sub {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--ui-muted);
  margin: 22px 0 12px;
  padding-top: 16px;
  border-top: 1px solid var(--ui-border);
}
.opts {
  justify-content: flex-end;
  gap: 8px;
}
.actions-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.copy {
  cursor: pointer;
  word-break: break-all;
  margin: 0 4px;
}
.hint {
  font-size: 0.8rem;
}
</style>
