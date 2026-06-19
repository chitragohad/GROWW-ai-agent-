---
name: Groww Weekly Pulse
colors:
  surface: '#fcf8fa'
  surface-dim: '#dcd9db'
  surface-bright: '#fcf8fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f5'
  surface-container: '#f0edef'
  surface-container-high: '#eae7e9'
  surface-container-highest: '#e4e2e4'
  on-surface: '#1b1b1d'
  on-surface-variant: '#45464d'
  inverse-surface: '#303032'
  inverse-on-surface: '#f3f0f2'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#271901'
  on-tertiary-container: '#98805d'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#fcdeb5'
  tertiary-fixed-dim: '#dec29a'
  on-tertiary-fixed: '#271901'
  on-tertiary-fixed-variant: '#574425'
  background: '#fcf8fa'
  on-background: '#1b1b1d'
  surface-variant: '#e4e2e4'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  container-max: 1440px
  gutter: 16px
  margin-mobile: 16px
  margin-desktop: 32px
  stack-xs: 4px
  stack-sm: 8px
  stack-md: 16px
  table-cell-padding: 10px 12px
---

## Brand & Style
The design system focuses on high-utility, internal fintech operations. It prioritizes information density and clarity over decorative elements, adopting a hybrid aesthetic inspired by modern developer tools and minimalist productivity software. 

The visual style is characterized by a "Structured Minimalism." It utilizes a neutral, low-contrast foundation to ensure that status indicators and data points remain the primary focus. The interface relies on subtle 1px borders and rhythmic spacing rather than heavy shadows or vibrant backgrounds, creating a calm, professional environment for managing complex financial workflows.

## Colors
The palette is rooted in the "Slate" scale to provide an enterprise-grade feel. 

- **Foundation**: The application background uses a very light slate tint to differentiate from white surface cards and input fields.
- **Primary**: Slate-900 is reserved for primary actions, navigation headers, and high-emphasis text.
- **Accents**: Status colors use standard utility tones but are applied with low-saturation backgrounds and high-saturation text/icons to maintain readability within dense tables.
- **Borders**: A consistent `Slate-200` is used for all structural lines, ensuring the "Notion-like" grid feel.

## Typography
The typographic scale is compact to support data-dense layouts. 

- **Inter** is the workhorse for all UI elements, labels, and body text. Tight letter spacing is applied to headlines to mimic the "Linear" aesthetic.
- **JetBrains Mono** is strictly reserved for technical identifiers, such as `run_id`, `transaction_hash`, and timestamps. This font switch signals to the user that the content is a precise system value that can be copied or filtered.
- **Hierarchy**: Use `body-sm` for the majority of table content to maximize visible rows.

## Layout & Spacing
The layout follows a strict functional grid. 

- **Navigation**: A fixed left-hand sidebar (240px) for high-level module switching.
- **Grid**: A 12-column fluid system for dashboard widgets (KPI cards), while the main "Pulse" view uses a full-width fluid layout for data tables.
- **Density**: Spacing is intentionally tight. Vertical rhythm follows a 4px baseline. Table rows should have a fixed height of 40px to 44px to ensure high information density without sacrificing legibility.
- **Breakpoints**: 
    - Mobile (<768px): Single column, hidden sidebar (hamburger menu).
    - Desktop (>1024px): Standard 2-column layout (Sidebar + Content).

## Elevation & Depth
In line with the "Notion/Linear" aesthetic, this design system avoids heavy drop shadows. 

- **Layer 0 (Background)**: `Slate-50` or `#F8FAFC`.
- **Layer 1 (Surface)**: White cards and containers use a 1px border of `Slate-200`. No shadow.
- **Layer 2 (Overlays)**: Modals and dropdowns use a very soft, high-diffusion shadow (`0 10px 15px -3px rgba(0,0,0,0.05)`) and a 1px border to separate from the background.
- **Hover States**: Use `Slate-50` as a background fill for interactive list items or table rows to indicate focus.

## Shapes
The shape language is "Soft" yet disciplined. 

- **Standard Elements**: Buttons, inputs, and cards use a `4px` (0.25rem) radius to maintain a precise, professional look.
- **Status Pills**: Use a fully rounded (pill) shape to distinguish them from interactive buttons.
- **Data Cards**: Should use the same 4px radius as inputs to ensure a cohesive "boxed" appearance across the dashboard.

## Components

### Status Pills
Pills use a "Tinted" style: a light background version of the status color with high-contrast text.
- **Completed**: Background `Green-50`, Text `Green-700`, 1px Border `Green-200`.
- **Failed**: Background `Red-50`, Text `Red-700`, 1px Border `Red-200`.
- **Running**: Background `Blue-50`, Text `Blue-700`, 1px Border `Blue-200`.

### KPI Cards
Minimalist containers with a `label-caps` title in `Slate-500` at the top and a `headline-lg` value in `Slate-900` in the center. Use 1px borders; do not use background fills for cards.

### Data Tables
- **Header**: `Slate-50` background with `label-caps` text. 1px bottom border.
- **Rows**: White background. On hover, change background to `Slate-50`. 
- **Monospace Cells**: Any cell containing IDs or numerical sequences must use `data-mono`.

### Input Fields
Strict 1px `Slate-200` border. On focus, the border changes to `Slate-900` or a 1px ring. Use `body-sm` for input text.

### Alert Banners
Positioned at the top of the content area. Use a solid 1px border corresponding to the severity (Amber/Red) and a subtle left-edge accent bar (3px width) in the same color for quick visual scanning.