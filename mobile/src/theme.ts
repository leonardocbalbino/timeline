// Tokens da marca Íntegra (os mesmos do site: static/css/tokens.css).
export const colors = {
  ink: '#0E1A2B',
  ink2: '#1B2B44',
  text: '#0E1A2B',
  textMuted: '#3B4B62',
  textSubtle: '#5A6B82',
  bg: '#F5F6F8',
  surface: '#FFFFFF',
  surface2: '#EEF1F5',
  border: '#E2E6EC',
  borderStrong: '#C9D1DC',
  action: '#2443B8',
  actionPressed: '#1A3290',
  verified: '#0F766E',
  verifiedBg: '#E3F4F1',
  verifiedBright: '#2DD4BF',
  highlight: '#B45309',
  highlightText: '#8A4006',
  highlightBg: '#FDF0E1',
  warningBg: '#FDF0E1',
  warningText: '#6B3505',
  danger: '#B42318',
  dangerBg: '#FDECEA',
  onDarkMuted: '#B7C4D6',
} as const;

export const fonts = {
  display: 'SchibstedGrotesk_700Bold',
  displayHeavy: 'SchibstedGrotesk_800ExtraBold',
  body: 'PublicSans_400Regular',
  bodyMedium: 'PublicSans_500Medium',
  bodySemi: 'PublicSans_600SemiBold',
  mono: 'IBMPlexMono_400Regular',
  monoMedium: 'IBMPlexMono_500Medium',
} as const;

export const radius = { sm: 8, md: 10, lg: 14, xl: 20, pill: 999 } as const;
export const space = { 1: 4, 2: 8, 3: 12, 4: 16, 5: 20, 6: 24, 8: 32, 10: 40, 12: 48 } as const;
