// Logo shipped with the application, used wherever branding defines none.
export const DEFAULT_LOGO = '/logo.png'
export const DEFAULT_FAVICON = '/favicon.png'

// Default colours taken from Homer
export const DEFAULT_COLORS = {
  light: {
    highlight_primary: '#3367d6',
    highlight_secondary: '#4285f4',
    highlight_hover: '#5a95f5',
    background: '#f5f5f5',
    card_background: '#ffffff',
    text: '#363636',
    text_header: '#ffffff',
    text_title: '#303030',
    text_subtitle: '#424242',
    link: '#3273dc',
  },
  dark: {
    highlight_primary: '#3367d6',
    highlight_secondary: '#4285f4',
    highlight_hover: '#5a95f5',
    background: '#131313',
    card_background: '#2b2b2b',
    text: '#eaeaea',
    text_header: '#ffffff',
    text_title: '#fafafa',
    text_subtitle: '#f5f5f5',
    link: '#3273dc',
  },
}

export const COLOR_LABELS = {
  highlight_primary: 'Header',
  highlight_secondary: 'Navigation bar',
  highlight_hover: 'Hover',
  background: 'Page background',
  card_background: 'Card background',
  text: 'Text',
  text_header: 'Header text',
  text_title: 'Card title',
  text_subtitle: 'Card subtitle',
  link: 'Links',
}

export function emptyConfig() {
  return {
    columns: '3',
    default_theme: 'auto',
    default_layout: 'columns',
    show_header: true,
    status_interval: 60,
    footer: '',
    background: { type: 'default', color: '', gradient_from: '', gradient_to: '', gradient_angle: 135, image: '', overlay: 0, blur: 0 },
    colors: {
      light: Object.fromEntries(Object.keys(DEFAULT_COLORS.light).map((k) => [k, ''])),
      dark: Object.fromEntries(Object.keys(DEFAULT_COLORS.dark).map((k) => [k, ''])),
    },
    message: { enabled: false, style: 'is-info', title: '', icon: '', content: '' },
    links: [],
    sections: [],
  }
}

export function uid() {
  return Math.random().toString(36).slice(2, 10)
}

// Sign-in page background, shared by the sign-in page and the Branding preview.
export function loginBackground(b = {}) {
  const primary = b.primary_color || '#3367d6'
  const fallback = { backgroundImage: `linear-gradient(135deg, ${primary}, color-mix(in srgb, ${primary} 45%, #0b1020))` }
  let style = fallback
  switch (b.login_bg_type) {
    case 'color':
      style = { background: b.login_bg_color || primary }
      break
    case 'gradient':
      style = {
        backgroundImage: `linear-gradient(${b.login_bg_gradient_angle ?? 135}deg, ${b.login_bg_gradient_from || primary}, ${b.login_bg_gradient_to || '#0b1020'})`,
      }
      break
    case 'image':
      if (b.login_background) {
        style = {
          backgroundImage: `url("${b.login_background}")`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          filter: b.login_bg_blur ? `blur(${b.login_bg_blur}px)` : null,
          inset: b.login_bg_blur ? `-${b.login_bg_blur * 2}px` : 0,
        }
      }
      break
    default:
      // Backward compatibility: an image set before the background type existed
      if (b.login_background && !b.login_bg_type) style = { backgroundImage: `url("${b.login_background}")`, backgroundSize: 'cover', backgroundPosition: 'center' }
  }
  const overlay = b.login_bg_type === 'image' && b.login_background ? Number(b.login_bg_overlay || 0) : 0
  return { style, overlay }
}
