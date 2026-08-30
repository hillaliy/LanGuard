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
  IconNetworkOff,
  IconRadar,
  IconShieldX,
} from '@tabler/icons-react';

export default function NotFound() {
  return (
    <main className="not-found-shell">
      <Container size={760}>
        <Stack align="center" gap="xl" ta="center">
          <Box className="not-found-visual" aria-hidden="true">
            <Text className="not-found-code">404</Text>
            <Box className="not-found-logo">
              <Image src="/logo.png" alt="" h={88} w={88} fit="contain" />
            </Box>
            <Box className="not-found-node node-one">
              <IconRadar size={22} />
            </Box>
            <Box className="not-found-node node-two">
              <IconNetworkOff size={22} />
            </Box>
            <Box className="not-found-node node-three">
              <IconShieldX size={22} />
            </Box>
          </Box>

          <Stack align="center" gap="sm">
            <Title order={1} className="not-found-title">
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
