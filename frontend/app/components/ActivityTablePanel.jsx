'use client';

import { useEffect, useRef } from 'react';
import { Box, Group, Loader, Paper, ScrollArea } from '@mantine/core';

export default function ActivityTablePanel({
  children,
  hasMore = false,
  loadingMore = false,
  onLoadMore,
}) {
  const viewportRef = useRef(null);
  const loadRequestedRef = useRef(false);

  useEffect(() => {
    if (!loadingMore) {
      loadRequestedRef.current = false;
    }
  }, [loadingMore]);

  function handleScrollPositionChange() {
    const viewport = viewportRef.current;
    if (!viewport || !hasMore || loadingMore || loadRequestedRef.current || !onLoadMore) {
      return;
    }

    const remaining = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    if (remaining < 140) {
      loadRequestedRef.current = true;
      onLoadMore();
    }
  }

  return (
    <Paper className="content-panel activity-table-panel" radius="md">
      <ScrollArea
        viewportRef={viewportRef}
        h="min(640px, calc(100vh - 250px))"
        offsetScrollbars
        scrollbarSize={10}
        type="always"
        onScrollPositionChange={handleScrollPositionChange}
      >
        <Box className="activity-table-scroll">
          {children}
          {hasMore && (
            <Group justify="center" p="md">
              <Loader size="sm" />
            </Group>
          )}
        </Box>
      </ScrollArea>
    </Paper>
  );
}
