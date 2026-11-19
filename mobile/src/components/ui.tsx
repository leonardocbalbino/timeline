import type { LucideIcon } from 'lucide-react-native';
import type { ReactNode } from 'react';
import {
  ActivityIndicator, Pressable, Text as RNText, TextInput, View,
  type PressableProps, type StyleProp, type TextInputProps, type TextProps, type TextStyle, type ViewStyle,
} from 'react-native';
import Svg, { Circle, Line, Path, Rect } from 'react-native-svg';

import { colors, fonts, radius, space } from '@/theme';

// ------------------------------------------------------------ texto
type Variant = 'h1' | 'h2' | 'h3' | 'body' | 'muted' | 'subtle' | 'small' | 'mono' | 'label' | 'eyebrow';
const variants: Record<Variant, TextStyle> = {
  h1: { fontFamily: fonts.display, fontSize: 30, lineHeight: 35, letterSpacing: -0.6, color: colors.text },
  h2: { fontFamily: fonts.display, fontSize: 20, lineHeight: 26, letterSpacing: -0.2, color: colors.text },
  h3: { fontFamily: fonts.bodySemi, fontSize: 17, lineHeight: 23, color: colors.text },
  body: { fontFamily: fonts.body, fontSize: 16, lineHeight: 24, color: colors.text },
  muted: { fontFamily: fonts.body, fontSize: 15, lineHeight: 22, color: colors.textMuted },
  subtle: { fontFamily: fonts.body, fontSize: 14, lineHeight: 20, color: colors.textSubtle },
  small: { fontFamily: fonts.body, fontSize: 13, lineHeight: 18, color: colors.textSubtle },
  mono: { fontFamily: fonts.mono, fontSize: 13, lineHeight: 18, color: colors.textMuted },
  label: { fontFamily: fonts.bodySemi, fontSize: 14, lineHeight: 20, color: colors.text },
  eyebrow: { fontFamily: fonts.monoMedium, fontSize: 12, lineHeight: 16, letterSpacing: 1, textTransform: 'uppercase', color: colors.verified },
};

export function Text({ variant = 'body', style, ...rest }: TextProps & { variant?: Variant }) {
  return <RNText {...rest} style={[variants[variant], style]} />;
}

// ------------------------------------------------------------ botões
type ButtonKind = 'primary' | 'secondary' | 'dark' | 'ghost' | 'danger';
const buttonColors: Record<ButtonKind, { bg: string; fg: string; border?: string; pressed: string }> = {
  primary: { bg: colors.action, fg: '#fff', pressed: colors.actionPressed },
  secondary: { bg: colors.surface, fg: colors.ink, border: colors.borderStrong, pressed: colors.surface2 },
  dark: { bg: colors.ink, fg: '#fff', pressed: colors.ink2 },
  ghost: { bg: 'transparent', fg: colors.action, pressed: colors.surface2 },
  danger: { bg: colors.danger, fg: '#fff', pressed: '#8F1C13' },
};

export function Button({
  title, onPress, kind = 'primary', icon: Icon, loading, disabled, small, style, accessibilityLabel,
}: {
  title?: string; onPress?: PressableProps['onPress']; kind?: ButtonKind; icon?: LucideIcon; loading?: boolean;
  disabled?: boolean; small?: boolean; style?: StyleProp<ViewStyle>; accessibilityLabel?: string;
}) {
  const c = buttonColors[kind];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? title}
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [{
        minHeight: small ? 40 : 48, paddingHorizontal: title ? (small ? 14 : 18) : 12, borderRadius: radius.md,
        backgroundColor: pressed ? c.pressed : c.bg, borderWidth: c.border ? 1 : 0, borderColor: c.border,
        flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
        opacity: disabled ? 0.5 : 1,
      }, style]}
    >
      {loading ? <ActivityIndicator color={c.fg} /> : Icon ? <Icon size={18} color={c.fg} strokeWidth={2} /> : null}
      {title ? <RNText style={{ fontFamily: fonts.bodySemi, fontSize: small ? 14 : 15, color: c.fg }}>{title}</RNText> : null}
    </Pressable>
  );
}

// ------------------------------------------------------------ formulário
export function Field({ label, hint, style, ...input }: TextInputProps & { label: string; hint?: string }) {
  return (
    <View style={{ gap: 6 }}>
      <Text variant="label">{label}{hint ? <Text variant="small">  {hint}</Text> : null}</Text>
      <TextInput
        placeholderTextColor={colors.textSubtle}
        {...input}
        style={[{
          minHeight: 48, borderWidth: 1, borderColor: colors.borderStrong, borderRadius: radius.md,
          paddingHorizontal: 14, paddingVertical: 12, fontFamily: fonts.body, fontSize: 16, color: colors.text,
          backgroundColor: colors.surface, textAlignVertical: input.multiline ? 'top' : 'center',
        }, style]}
      />
    </View>
  );
}

// ------------------------------------------------------------ superfícies
export function Card({ children, style, padded = true }: { children: ReactNode; style?: StyleProp<ViewStyle>; padded?: boolean }) {
  return (
    <View style={[{
      backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border,
      padding: padded ? space[5] : 0,
    }, style]}>{children}</View>
  );
}

type ChipKind = 'default' | 'highlight' | 'verified' | 'warning' | 'danger' | 'dark';
const chipColors: Record<ChipKind, { bg: string; fg: string }> = {
  default: { bg: colors.surface2, fg: colors.textMuted },
  highlight: { bg: colors.highlightBg, fg: colors.highlightText },
  verified: { bg: colors.verifiedBg, fg: colors.verified },
  warning: { bg: colors.warningBg, fg: colors.warningText },
  danger: { bg: colors.dangerBg, fg: colors.danger },
  dark: { bg: colors.ink, fg: '#fff' },
};
export function Chip({ label, kind = 'default', icon: Icon }: { label: string; kind?: ChipKind; icon?: LucideIcon }) {
  const c = chipColors[kind];
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: c.bg, borderRadius: radius.pill,
      paddingHorizontal: 10, paddingVertical: 4, alignSelf: 'flex-start' }}>
      {Icon ? <Icon size={13} color={c.fg} /> : null}
      <RNText style={{ fontFamily: kind === 'default' ? fonts.bodyMedium : fonts.bodySemi, fontSize: 13, color: c.fg }}>{label}</RNText>
    </View>
  );
}

export function Empty({ icon: Icon, title, text, children }: { icon: LucideIcon; title: string; text?: string; children?: ReactNode }) {
  return (
    <View style={{ alignItems: 'center', gap: space[3], paddingVertical: space[12], paddingHorizontal: space[6] }}>
      <Icon size={26} color={colors.textSubtle} />
      <Text variant="h3" style={{ textAlign: 'center' }}>{title}</Text>
      {text ? <Text variant="muted" style={{ textAlign: 'center' }}>{text}</Text> : null}
      {children}
    </View>
  );
}

export function Notice({ text, kind = 'danger' }: { text: string; kind?: 'danger' | 'warning' | 'info' }) {
  const bg = kind === 'danger' ? colors.dangerBg : kind === 'warning' ? colors.warningBg : colors.surface2;
  const fg = kind === 'danger' ? colors.danger : kind === 'warning' ? colors.warningText : colors.ink;
  return (
    <View accessibilityRole="alert" style={{ backgroundColor: bg, borderRadius: radius.md, padding: space[3] }}>
      <RNText style={{ fontFamily: fonts.body, fontSize: 14, lineHeight: 20, color: fg }}>{text}</RNText>
    </View>
  );
}

// ------------------------------------------------------------ marca
export function LogoMark({ size = 32, dark = false }: { size?: number; dark?: boolean }) {
  const base = dark ? '#1B2B44' : '#0E1A2B';
  return (
    <Svg width={size} height={size} viewBox="0 0 40 40" accessibilityLabel="Íntegra">
      <Rect width={40} height={40} rx={10} fill={base} />
      <Line x1={20} y1={9} x2={20} y2={31} stroke="#5B7192" strokeWidth={2.4} strokeLinecap="round" />
      <Circle cx={20} cy={11} r={3.1} fill={base} stroke="#FFFFFF" strokeWidth={2.1} />
      <Circle cx={20} cy={20} r={4.8} fill="#2DD4BF" />
      <Path d="M17.9 20.1l1.5 1.5 2.9-3" fill="none" stroke="#0E1A2B" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" />
      <Circle cx={20} cy={29} r={3.1} fill={base} stroke="#FFFFFF" strokeWidth={2.1} />
    </Svg>
  );
}

export function Logo({ dark = false }: { dark?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <LogoMark dark={dark} />
      <RNText style={{ fontFamily: fonts.displayHeavy, fontSize: 22, letterSpacing: -0.4, color: dark ? '#fff' : colors.ink }}>íntegra</RNText>
    </View>
  );
}
