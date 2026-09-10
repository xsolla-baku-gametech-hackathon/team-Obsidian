// Synthetic UI fixtures. Replace this module with the versioned API/snapshot adapter.
export const weeks = ['Sep 14', 'Sep 21', 'Sep 28', 'Oct 5', 'Oct 12', 'Oct 19', 'Oct 26', 'Nov 2'];
export const segments = ['Action', 'Indie strategy', 'Cozy'] as const;
export type Segment = typeof segments[number];
export const counts: Record<Segment, number[]> = { Action: [18, 24, 12, 7, 15, 21, 10, 16], 'Indie strategy': [12, 16, 8, 3, 9, 14, 6, 11], Cozy: [6, 9, 4, 2, 7, 8, 3, 5] };
// Recommendation results are fixture responses, not browser-generated scores.
export const recommendations: Record<Segment, { week: string; count: number; comparison: string }> = { Action: { week: 'Oct 5 – 11', count: 7, comparison: 'Action' }, 'Indie strategy': { week: 'Oct 5 – 11', count: 3, comparison: 'Indie strategy' }, Cozy: { week: 'Oct 5 – 11', count: 2, comparison: 'Cozy' } };
export const games = [
  { id: 646570, name: 'Slay the Spire', genre: 'Indie strategy', tags: 'Deckbuilder · Roguelike', week: 1, day: 'Sep 23', color: '#a87750', initials: 'SS' },
  { id: 1940340, name: 'Darkest Dungeon II', genre: 'Indie strategy', tags: 'Turn-based · Roguelike', week: 2, day: 'Sep 29', color: '#635576', initials: 'DD' },
  { id: 1145360, name: 'Hades', genre: 'Action', tags: 'Action · Roguelike', week: 0, day: 'Sep 17', color: '#a45052', initials: 'H' },
  { id: 588650, name: 'Dead Cells', genre: 'Action', tags: 'Action · Platformer', week: 4, day: 'Oct 15', color: '#4e7681', initials: 'DC' },
  { id: 413150, name: 'Stardew Valley', genre: 'Cozy', tags: 'Farming · Life sim', week: 2, day: 'Oct 1', color: '#8b985b', initials: 'SV' },
  { id: 1336490, name: 'Against the Storm', genre: 'Indie strategy', tags: 'City builder · Strategy', week: 5, day: 'Oct 22', color: '#4d7b69', initials: 'AS' },
  { id: 1158160, name: 'Coral Island', genre: 'Cozy', tags: 'Farming · Adventure', week: 6, day: 'Oct 28', color: '#528d94', initials: 'CI' },
];
export const creators = [
 { name: 'Pixel & Potion', handle: '@pixelandpotion', platform: 'YouTube', audience: '42.8K', genre: 'Indie strategy', match: 96, initials: 'PP', color: '#e9e1fb' },
 { name: 'The Cozy Corner', handle: '@cozycorner', platform: 'Twitch', audience: '18.2K', genre: 'Cozy', match: 94, initials: 'CC', color: '#f5e7d9' },
 { name: 'Rogue Runner', handle: '@roguerunner', platform: 'Twitch', audience: '31.6K', genre: 'Action', match: 91, initials: 'RR', color: '#dcebe4' },
 { name: 'Turn by Turn', handle: '@turnbyturn', platform: 'YouTube', audience: '26.4K', genre: 'Indie strategy', match: 89, initials: 'TT', color: '#dfe8f7' },
];
