/** Capitalises the string. */
function capitaliseString(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function undocumentedAdd(a: number, b: number): number {
  return a + b;
}

// autodoc: ignore
function ignoredByMarker(): void {}

/** Doubles every even value, dropping odd ones. */
const doubleEvens = (values: number[]): number[] => {
  return values.filter((v) => v % 2 === 0).map((v) => v * 2);
};

export function exportedFetch(url: string): Promise<Response> {
  return fetch(url);
}

/**
 * Looks up a value, cached because the backing store is a slow network call.
 */
export class Cache {
  private store: Map<string, string> = new Map();

  /** Reads a value from the cache. */
  get(key: string): string | undefined {
    return this.store.get(key);
  }

  set(key: string, value: string): void {
    this.store.set(key, value);
  }
}
