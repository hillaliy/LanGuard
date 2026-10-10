'use client';

import { useEffect, useState } from 'react';
import {
  ActionIcon,
  Alert,
  Box,
  Button,
  Group,
  Modal,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import {
  IconAlertCircle,
  IconArrowDown,
  IconArrowUp,
  IconEdit,
  IconExternalLink,
  IconLink,
  IconPlus,
  IconTrash,
  IconWorld,
} from '@tabler/icons-react';

import { apiRequest } from '../api';
import { validExternalUrl } from '../utils/device';

export default function DeviceRelatedLinksSection({
  deviceId,
  editing,
  initialLinks = [],
  onError,
  onLinksChange,
  onSuccess,
}) {
  const [links, setLinks] = useState(initialLinks);
  const [editorOpened, setEditorOpened] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [editingLink, setEditingLink] = useState(null);
  const [label, setLabel] = useState('');
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLinks(initialLinks);
  }, [deviceId, initialLinks]);

  function openCreate() {
    setEditingLink(null);
    setLabel('');
    setUrl('');
    setError('');
    setEditorOpened(true);
  }

  function openEdit(link) {
    setEditingLink(link);
    setLabel(link.label);
    setUrl(link.url);
    setError('');
    setEditorOpened(true);
  }

  function applyPayload(payload) {
    const nextLinks = payload?.data || [];
    setLinks(nextLinks);
    onLinksChange?.(nextLinks);
    onSuccess?.(payload);
  }

  async function saveLink() {
    if (!label.trim()) {
      setError('Link label is required.');
      return;
    }
    if (!url.trim() || !validExternalUrl(url)) {
      setError('Enter a valid HTTP or HTTPS URL without embedded credentials.');
      return;
    }

    setSaving(true);
    setError('');
    try {
      const payload = await apiRequest('device/links/', {
        method: editingLink ? 'PUT' : 'POST',
        params: {
          id: deviceId,
          link_id: editingLink?.id,
        },
        body: { label: label.trim(), url: url.trim() },
      });
      applyPayload(payload);
      setEditorOpened(false);
    } catch (requestError) {
      setError(requestError.message);
      onError?.(requestError);
    } finally {
      setSaving(false);
    }
  }

  async function deleteLink() {
    if (!deleteTarget) return;
    setSaving(true);
    try {
      const payload = await apiRequest('device/links/', {
        method: 'DELETE',
        params: { id: deviceId, link_id: deleteTarget.id },
      });
      applyPayload(payload);
      setDeleteTarget(null);
    } catch (requestError) {
      onError?.(requestError);
    } finally {
      setSaving(false);
    }
  }

  async function moveLink(index, offset) {
    const destination = index + offset;
    if (destination < 0 || destination >= links.length) return;
    const reordered = [...links];
    [reordered[index], reordered[destination]] = [reordered[destination], reordered[index]];
    setSaving(true);
    try {
      const payload = await apiRequest('device/links/', {
        method: 'PATCH',
        params: { id: deviceId },
        body: { order: reordered.map((link) => link.id) },
      });
      applyPayload(payload);
    } catch (requestError) {
      setLinks(links);
      onError?.(requestError);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Box className="device-related-links">
      <Group justify="space-between" align="center" mb="sm">
        <Group gap="xs">
          <IconLink size={18} aria-hidden="true" />
          <Title order={5}>Related links</Title>
        </Group>
        {editing && (
          <Button
            size="compact-sm"
            variant="light"
            leftSection={<IconPlus size={16} />}
            onClick={openCreate}
          >
            Add link
          </Button>
        )}
      </Group>

      {links.length ? (
        <Stack gap="xs">
          {links.map((link, index) => (
            <Group key={link.id} className="device-related-link-row" wrap="nowrap">
              <UnstyledButton
                component="a"
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="device-related-link-anchor"
                aria-label={`Open ${link.label} in a new tab`}
              >
                <Box className="device-related-link-icon">
                  <IconWorld size={19} aria-hidden="true" />
                </Box>
                <Box className="device-related-link-copy">
                  <Text fw={700} truncate>{link.label}</Text>
                  <Text size="xs" c="dimmed" truncate>{link.url}</Text>
                </Box>
                <IconExternalLink size={17} aria-hidden="true" />
              </UnstyledButton>
              {editing && (
                <Group gap={4} wrap="nowrap" className="device-related-link-actions">
                  <Tooltip label="Move link up">
                    <ActionIcon
                      variant="subtle"
                      aria-label={`Move ${link.label} up`}
                      disabled={saving || index === 0}
                      onClick={() => moveLink(index, -1)}
                    >
                      <IconArrowUp size={17} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Move link down">
                    <ActionIcon
                      variant="subtle"
                      aria-label={`Move ${link.label} down`}
                      disabled={saving || index === links.length - 1}
                      onClick={() => moveLink(index, 1)}
                    >
                      <IconArrowDown size={17} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Edit link">
                    <ActionIcon
                      variant="subtle"
                      aria-label={`Edit ${link.label}`}
                      disabled={saving}
                      onClick={() => openEdit(link)}
                    >
                      <IconEdit size={17} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label="Delete link">
                    <ActionIcon
                      variant="subtle"
                      color="red"
                      aria-label={`Delete ${link.label}`}
                      disabled={saving}
                      onClick={() => setDeleteTarget(link)}
                    >
                      <IconTrash size={17} />
                    </ActionIcon>
                  </Tooltip>
                </Group>
              )}
            </Group>
          ))}
        </Stack>
      ) : (
        <Text size="sm" c="dimmed">
          {editing ? 'No related links. Add manuals, invoices, diagrams, or support pages.' : 'No related links added.'}
        </Text>
      )}

      <Modal
        opened={editorOpened}
        onClose={() => !saving && setEditorOpened(false)}
        title={editingLink ? 'Edit related link' : 'Add related link'}
        centered
      >
        <Stack>
          {error && <Alert color="red" icon={<IconAlertCircle size={18} />}>{error}</Alert>}
          <TextInput
            label="Label"
            placeholder="User manual"
            value={label}
            onChange={(event) => setLabel(event.currentTarget.value)}
            maxLength={100}
            required
          />
          <TextInput
            label="URL"
            placeholder="https://example.com/manual.pdf"
            value={url}
            onChange={(event) => setUrl(event.currentTarget.value)}
            required
          />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setEditorOpened(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={saveLink} loading={saving}>
              {editingLink ? 'Save link' : 'Add link'}
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal
        opened={Boolean(deleteTarget)}
        onClose={() => !saving && setDeleteTarget(null)}
        title="Delete related link"
        centered
      >
        <Stack>
          <Text>Remove {deleteTarget?.label} from this device?</Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDeleteTarget(null)} disabled={saving}>
              Cancel
            </Button>
            <Button color="red" onClick={deleteLink} loading={saving}>
              Delete link
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Box>
  );
}
