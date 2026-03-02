const isDev = import.meta.env.DEV;

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

export interface ErrorTracker {
  captureError(message: string, data?: unknown): void;
}

const noopTracker: ErrorTracker = {
  captureError: () => undefined,
};

let _tracker: ErrorTracker = noopTracker;

/** Configure an external error tracker (e.g. Sentry). Call once at app startup. */
export function configureLogger(tracker: ErrorTracker): void {
  _tracker = tracker;
}

function log(level: LogLevel, message: string, data?: unknown): void {
  if (!isDev) return;
  const timestamp = new Date().toISOString();
  const prefix = `[${timestamp}] [${level.toUpperCase()}]`;
  if (data !== undefined) {
    console[level === 'debug' ? 'log' : level](`${prefix} ${message}`, data);
  } else {
    console[level === 'debug' ? 'log' : level](`${prefix} ${message}`);
  }
}

export const logger = {
  debug: (message: string, data?: unknown) => log('debug', message, data),
  info: (message: string, data?: unknown) => log('info', message, data),
  warn: (message: string, data?: unknown) => log('warn', message, data),
  error: (message: string, data?: unknown) => {
    log('error', message, data);
    if (!isDev) {
      _tracker.captureError(message, data);
    }
  },
};
