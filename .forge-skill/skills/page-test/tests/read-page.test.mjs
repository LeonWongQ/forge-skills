import assert from 'node:assert/strict';
import test from 'node:test';

import { extractContent } from '../scripts/read-page.mjs';


function pageWith(values) {
  return {
    async waitForFunction(_callback, selectors) {
      const selector = selectors.find((item) => values[item]?.visible && values[item]?.content.trim());
      if (!selector) {
        const error = new Error('timed out');
        error.name = 'TimeoutError';
        throw error;
      }
      return { async jsonValue() { return selector; } };
    },
    locator(selector) {
      const value = values[selector] || { visible: false, content: '' };
      return {
        first() {
          return {
            async isVisible() { return value.visible; },
            async innerText() { return value.content; },
            async waitFor() {
              if (!value.visible) throw new Error('not visible');
            },
          };
        },
      };
    },
  };
}


test('semantic main content is selected before body fallback', async () => {
  const result = await extractContent(pageWith({
    main: { visible: true, content: 'Article text' },
    body: { visible: true, content: 'Navigation\nArticle text\nFooter' },
  }), ['main', 'article', 'body']);

  assert.deepEqual(result, { content: 'Article text', selector: 'main' });
});


test('empty semantic containers fall back to body', async () => {
  const result = await extractContent(pageWith({
    main: { visible: true, content: '   ' },
    body: { visible: true, content: 'Fallback text' },
  }), ['main', 'body']);

  assert.deepEqual(result, { content: 'Fallback text', selector: 'body' });
});


test('explicit selector timeout does not silently fall back to body', async () => {
  await assert.rejects(
    extractContent(pageWith({
      '.content': { visible: false, content: '' },
      body: { visible: true, content: 'Loading' },
    }), ['.content'], 50),
    { name: 'TimeoutError' },
  );
});
