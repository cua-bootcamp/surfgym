'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Synchronizes UI selections with the backend's flat `data.ui` map.
 *
 *  1) 주입(injection): `PUT/PATCH /api/state`로 `data.ui.<key>`를 써두면
 *     페이지 진입 시 그 값으로 복원된다. 즉 "필터가 걸린 상태"를 액션 재생
 *     없이 만들 수 있다.
 *  2) 관측(observation): 같은 경로를 읽어 채점한다.
 *
 * Flat keys keep state injection and observation compatible with the task
 * contract without requiring intermediate object creation.
 */

type UiState = Record<string, unknown>;

// 마운트 시 모든 훅이 각자 GET을 날리면, 쿠키가 아직 없을 때
// 요청마다 다른 user_id가 발급되는 경합이 생긴다. 한 번만 읽어 공유한다.
let uiStatePromise: Promise<UiState> | null = null;

function loadUiState(): Promise<UiState> {
  if (!uiStatePromise) {
    uiStatePromise = fetch('/api/state')
      .then((r) => r.json())
      .then((body) => ((body?.state?.data?.ui ?? {}) as UiState))
      .catch(() => ({}));
  }
  return uiStatePromise;
}

export function useSyncedState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(initial);
  const valueRef = useRef<T>(initial);

  useEffect(() => {
    let cancelled = false;

    loadUiState().then((ui) => {
      if (cancelled) return;
      const stored = ui[key];
      if (stored !== undefined) {
        valueRef.current = stored as T;
        setValue(stored as T);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [key]);

  const set = useCallback(
    (next: T | ((prev: T) => T)) => {
      const resolved =
        typeof next === 'function' ? (next as (prev: T) => T)(valueRef.current) : next;

      valueRef.current = resolved;
      setValue(resolved);

      uiStatePromise = null; // 다음 마운트가 최신값을 읽도록 캐시 무효화

      fetch('/api/state', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: { ui: { [key]: resolved } }, note: `ui:${key}` }),
      }).catch(() => {});
    },
    [key]
  );

  return [value, set] as const;
}
