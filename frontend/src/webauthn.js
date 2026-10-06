// WebAuthn helpers: JSON options from the server <-> browser credential objects.
// Written by hand (no PublicKeyCredential.parse*FromJSON) to support every current browser.

const b64urlToBuf = (s) => {
  const pad = '='.repeat((4 - (s.length % 4)) % 4)
  const bin = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'))
  return Uint8Array.from(bin, (c) => c.charCodeAt(0)).buffer
}
const bufToB64url = (buf) =>
  btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')

export const webauthnSupported = () => typeof window !== 'undefined' && !!window.PublicKeyCredential && window.isSecureContext

function explain(err) {
  if (err?.name === 'NotAllowedError') return new Error('The operation was cancelled or timed out.')
  if (err?.name === 'InvalidStateError') return new Error('This security key is already registered.')
  if (err?.name === 'SecurityError') return new Error('WebAuthn is refused for this address: check PUBLIC_URL matches the URL in your browser.')
  return err
}

export async function createCredential(options) {
  const publicKey = {
    ...options,
    challenge: b64urlToBuf(options.challenge),
    user: { ...options.user, id: b64urlToBuf(options.user.id) },
    excludeCredentials: (options.excludeCredentials || []).map((c) => ({ ...c, id: b64urlToBuf(c.id) })),
  }
  let cred
  try {
    cred = await navigator.credentials.create({ publicKey })
  } catch (e) {
    throw explain(e)
  }
  return {
    id: cred.id,
    rawId: bufToB64url(cred.rawId),
    type: cred.type,
    authenticatorAttachment: cred.authenticatorAttachment || undefined,
    clientExtensionResults: cred.getClientExtensionResults?.() || {},
    response: {
      clientDataJSON: bufToB64url(cred.response.clientDataJSON),
      attestationObject: bufToB64url(cred.response.attestationObject),
      transports: cred.response.getTransports?.() || [],
    },
  }
}

export async function getAssertion(options) {
  const publicKey = {
    ...options,
    challenge: b64urlToBuf(options.challenge),
    allowCredentials: (options.allowCredentials || []).map((c) => ({ ...c, id: b64urlToBuf(c.id) })),
  }
  let cred
  try {
    cred = await navigator.credentials.get({ publicKey })
  } catch (e) {
    throw explain(e)
  }
  return {
    id: cred.id,
    rawId: bufToB64url(cred.rawId),
    type: cred.type,
    authenticatorAttachment: cred.authenticatorAttachment || undefined,
    clientExtensionResults: cred.getClientExtensionResults?.() || {},
    response: {
      clientDataJSON: bufToB64url(cred.response.clientDataJSON),
      authenticatorData: bufToB64url(cred.response.authenticatorData),
      signature: bufToB64url(cred.response.signature),
      userHandle: cred.response.userHandle ? bufToB64url(cred.response.userHandle) : null,
    },
  }
}
