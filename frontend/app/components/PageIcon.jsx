import { ThemeIcon } from '@mantine/core';

export default function PageIcon({ children }) {
  return (
    <ThemeIcon className="page-icon" size={52} radius={12} variant="light">
      {children}
    </ThemeIcon>
  );
}
