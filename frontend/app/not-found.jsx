import {
  Box,
  Button,
  Container,
  Group,
  Image,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import {
  IconArrowLeft,
} from '@tabler/icons-react';
import classes from './not-found.module.css';

export default function NotFound() {
  return (
    <main className={classes.shell}>
      <Container size={760}>
        <Stack align="center" gap="xl" ta="center">
          <Box className={classes.visual} aria-hidden="true">
            <Text className={classes.digit}>4</Text>
            <Box className={classes.logo}>
              <Image src="/logo.png" alt="" h={88} w={88} fit="contain" />
            </Box>
            <Text className={classes.digit}>4</Text>
          </Box>

          <Stack align="center" gap="sm">
            <Title order={1} className={classes.title}>
              Route not found
            </Title>
            <Text c="dimmed" size="lg" maw={540}>
              This address is outside the monitored LanGuard interface. Return to
              the dashboard to review devices, scans, and events.
            </Text>
          </Stack>

          <Group justify="center">
            <Button
              component="a"
              href="/dashboard"
              size="md"
              leftSection={<IconArrowLeft size={18} />}
            >
              Back to dashboard
            </Button>
          </Group>
        </Stack>
      </Container>
    </main>
  );
}
