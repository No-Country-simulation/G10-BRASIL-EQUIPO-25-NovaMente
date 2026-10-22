import type { Preview } from '@storybook/nextjs-vite';
import { mswLoader } from 'msw-storybook-addon/csf3';
import { worker } from '../src/mocks/browser';
import { handlers } from '../src/mocks/handlers';
import '../src/app/globals.css';

const preview: Preview = {
  loaders: [
    mswLoader(async () => {
      await worker.start({ onUnhandledFrame: 'bypass' });
      return worker;
    }),
  ],
  parameters: {
    msw: { handlers },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },

    a11y: {
      // 'todo' - show a11y violations in the test UI only
      // 'error' - fail CI on a11y violations
      // 'off' - skip a11y checks entirely
      test: 'todo',
    },

    backgrounds: { disable: true },
  },
};

export default preview;
