export function steamLink(value: string): string | null {
  try {
    const url = new URL(value.trim());
    const match = url.pathname.match(/^\/app\/([1-9]\d*)(?:\/[^/]*)?\/?$/);
    const isSteamAppUrl = url.protocol === 'https:'
      && url.hostname === 'store.steampowered.com'
      && !url.port
      && !url.username
      && !url.password
      && match;

    return isSteamAppUrl ? `https://store.steampowered.com/app/${match[1]}/` : null;
  } catch {
    return null;
  }
}
