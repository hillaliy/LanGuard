import { createTheme } from '@mantine/core';

const roundedControl = { defaultProps: { radius: 'md' } };

export const theme = createTheme({
  primaryColor: 'indigo',
  fontFamily:
    'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  headings: {
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontWeight: '700',
  },
  defaultRadius: 'md',
  components: {
    ActionIcon: roundedControl,
    Button: roundedControl,
    MultiSelect: roundedControl,
    NumberInput: roundedControl,
    Paper: roundedControl,
    PasswordInput: roundedControl,
    Select: roundedControl,
    SegmentedControl: roundedControl,
    Textarea: roundedControl,
    TextInput: roundedControl,
  },
});
