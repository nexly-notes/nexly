import "@testing-library/jest-dom/vitest";

// ProseMirror (Tiptap) relies on DOM measurement APIs that jsdom does not
// implement; stub them so the editor can mount in tests.
function createDomRect(): DOMRect {
  const rect = {
    x: 0,
    y: 0,
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    width: 0,
    height: 0,
    toJSON: (): Record<string, number> => ({}),
  };
  return rect as DOMRect;
}

class StubDomRectList extends Array<DOMRect> {
  item(index: number): DOMRect | null {
    return this[index] ?? null;
  }
}

function createDomRectList(): DOMRectList {
  return new StubDomRectList() as unknown as DOMRectList;
}

document.elementFromPoint = (): Element | null => null;
HTMLElement.prototype.getBoundingClientRect = createDomRect;
HTMLElement.prototype.getClientRects = createDomRectList;
Range.prototype.getBoundingClientRect = createDomRect;
Range.prototype.getClientRects = createDomRectList;
