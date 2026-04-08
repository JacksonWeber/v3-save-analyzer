/**
 * Data extractor for Victoria 3 save game data.
 *
 * Extracts structured metrics from parsed PDX data:
 * - GDP time series
 * - Population
 * - Budget (revenue/expenditure)
 * - Standard of living
 * - Military
 * - Technology
 * - Trade
 * - Top goods production
 */

import type {
  ParsedData,
  ParsedValue,
  MetaInfo,
  TimeseriesData,
  SnapshotData,
  StateInfo,
  TechInfo,
  GoodsInfo,
  CountryListItem,
  TerritoryMap,
  ExtractedData,
} from './types';

// ─── Local types ──────────────────────────────────────────────────────────

type CountryId = string | number | null;

interface ComparisonCountry {
  tag: string;
  name: string;
  isPlayer: boolean;
  timeseries: TimeseriesData;
}

// ─── Type-guard helpers ───────────────────────────────────────────────────

function isRecord(x: unknown): x is ParsedData {
  return typeof x === 'object' && x !== null && !Array.isArray(x);
}

function isNumber(x: unknown): x is number {
  return typeof x === 'number';
}

/** Compare two country-id values that may be string or number. */
function idsEqual(a: CountryId, b: CountryId): boolean {
  if (a === null || b === null) return false;
  return String(a) === String(b);
}

// ─── safeGet ──────────────────────────────────────────────────────────────

/** Safely look up a key in a parsed data object, trying both string and numeric key forms. */
function safeGet(
  d: ParsedValue,
  key: string | number,
  defaultVal: ParsedValue = {},
): ParsedValue {
  if (!isRecord(d)) return defaultVal;
  const strKey = String(key);
  if (strKey in d) return d[strKey];
  // Try alternative form (mirrors Python logic)
  if (typeof key === 'string') {
    const num = parseInt(key, 10);
    if (!isNaN(num)) {
      const altKey = String(num);
      if (altKey in d) return d[altKey];
    }
  }
  return defaultVal;
}

// ─── Country lookup helpers ───────────────────────────────────────────────

function getCountriesDb(gamestate: ParsedData): ParsedData {
  const cm = gamestate['country_manager'];
  if (isRecord(cm)) {
    const db = cm['database'];
    if (isRecord(db)) return db;
  }
  return {};
}

function getCountry(gamestate: ParsedData, countryId: CountryId): ParsedData {
  if (countryId === null) return {};
  const countries = getCountriesDb(gamestate);
  const result = safeGet(countries, countryId);
  return isRecord(result) ? result : {};
}

function getCountryName(countryData: ParsedValue, fallbackTag: string): string {
  if (isRecord(countryData)) {
    for (const key of ['definition', 'tag', 'country_type']) {
      if (key in countryData) {
        const val = countryData[key];
        if (typeof val === 'string' && val.length > 0) return val;
      }
    }
  }
  return fallbackTag;
}

function resolveCountryTag(gamestate: ParsedData, countryRef: ParsedValue): string {
  const countries = getCountriesDb(gamestate);
  const c = safeGet(countries, countryRef as string | number);
  if (isRecord(c) && 'definition' in c) {
    return String(c['definition']);
  }
  return String(countryRef);
}

function getPlayerTag(meta: ParsedData, gamestate: ParsedData): string {
  if (isRecord(meta)) {
    if ('player' in meta) return String(meta['player']);
    if ('player_tag' in meta) return String(meta['player_tag']);
  }
  const embedded = gamestate['meta_data'];
  if (isRecord(embedded)) {
    if ('player' in embedded) return String(embedded['player']);
    if ('player_tag' in embedded) return String(embedded['player_tag']);
  }
  if ('player_manager' in gamestate) {
    const pm = gamestate['player_manager'];
    if (isRecord(pm)) {
      if ('database' in pm) {
        const db = pm['database'];
        if (isRecord(db)) {
          for (const v of Object.values(db)) {
            if (isRecord(v) && 'country' in v) {
              return resolveCountryTag(gamestate, v['country']);
            }
          }
        }
      }
      if ('player_country' in pm) {
        return String(pm['player_country']);
      }
    }
  }
  if ('played_country' in gamestate) {
    const pc = gamestate['played_country'];
    if (isRecord(pc) && 'country' in pc) {
      return String(pc['country']);
    }
  }
  return 'UNKNOWN';
}

function findCountryId(gamestate: ParsedData, playerTag: string): CountryId {
  const countries = getCountriesDb(gamestate);
  for (const [cid, cdata] of Object.entries(countries)) {
    if (isRecord(cdata)) {
      if ('definition' in cdata && String(cdata['definition']) === playerTag) return cid;
      if ('tag' in cdata && String(cdata['tag']) === playerTag) return cid;
    }
  }
  const parsed = parseInt(playerTag, 10);
  if (!isNaN(parsed)) return parsed;
  return null;
}

function getGameDate(meta: ParsedData, gamestate: ParsedData): string {
  if (isRecord(meta) && 'date' in meta) return String(meta['date']);
  const embedded = gamestate['meta_data'];
  if (isRecord(embedded) && 'game_date' in embedded) return String(embedded['game_date']);
  if ('date' in gamestate) return String(gamestate['date']);
  return 'Unknown';
}

// ─── History extraction ───────────────────────────────────────────────────

function extractChannelValues(channelData: ParsedValue): ParsedValue[] {
  if (!isRecord(channelData)) return [];
  const channels = channelData['channels'];
  if (isRecord(channels)) {
    const ch0 = channels['0'];
    if (isRecord(ch0)) {
      const vals = ch0['values'];
      if (Array.isArray(vals)) return vals;
    }
  }
  return [];
}

function extractEmbeddedHistory(countryData: ParsedData): ParsedData {
  const history: ParsedData = {};
  const channelMap: Record<string, string> = {
    gdp: 'weekly_gdp',
    prestige: 'weekly_prestige',
    literacy: 'weekly_literacy',
    avgsoltrend: 'weekly_sol',
  };
  for (const [field, historyKey] of Object.entries(channelMap)) {
    if (!(field in countryData)) continue;
    const data = countryData[field];
    if (isRecord(data) && 'channels' in data) {
      const vals = extractChannelValues(data);
      if (vals.length > 0) history[historyKey] = vals;
    }
  }
  const ps = countryData['pop_statistics'];
  if (isRecord(ps)) {
    const tp = ps['trend_population'];
    if (isRecord(tp) && 'channels' in tp) {
      const vals = extractChannelValues(tp);
      if (vals.length > 0) history['weekly_population'] = vals;
    }
    if (!('weekly_population' in history)) {
      let totalPop = 0;
      for (const k of [
        'population_lower_strata',
        'population_middle_strata',
        'population_upper_strata',
      ]) {
        const v = ps[k];
        if (isNumber(v)) totalPop += v;
      }
      if (totalPop > 0) history['weekly_population'] = [totalPop];
    }
  }
  return history;
}

function getCountryHistory(gamestate: ParsedData, countryId: CountryId): ParsedData {
  let ch: ParsedValue = gamestate['country_history'] ?? {};
  if (isRecord(ch) && 'database' in ch) ch = ch['database'] ?? {};
  if (isRecord(ch) && countryId !== null) {
    const result = safeGet(ch, countryId);
    if (isRecord(result) && Object.keys(result).length > 0) return result;
  }
  const countryData = getCountry(gamestate, countryId);
  return extractEmbeddedHistory(countryData);
}

// ─── Timeseries extraction ────────────────────────────────────────────────

function extractTimeseries(history: ParsedValue): TimeseriesData {
  const timeseries: TimeseriesData = {};
  const keyMap: Record<string, string> = {
    weekly_gdp: 'gdp',
    weekly_money: 'treasury',
    weekly_population: 'population',
    weekly_sol: 'standard_of_living',
    weekly_revenue: 'revenue',
    weekly_expense: 'expenditure',
    weekly_literacy: 'literacy',
    weekly_prestige: 'prestige',
    weekly_clout: 'clout',
    weekly_innovations: 'innovations',
    weekly_military_strength: 'military_strength',
    weekly_gdp_per_capita: 'gdp_per_capita',
    gdp: 'gdp',
    money: 'treasury',
    population: 'population',
    sol: 'standard_of_living',
    revenue: 'revenue',
    expense: 'expenditure',
    literacy: 'literacy',
    prestige: 'prestige',
  };
  if (!isRecord(history)) return timeseries;

  for (const [saveKey, outputKey] of Object.entries(keyMap)) {
    if (saveKey in history) {
      const val = history[saveKey];
      if (Array.isArray(val)) {
        timeseries[outputKey] = val.map(v => (isNumber(v) ? v : 0.0));
      } else if (isNumber(val)) {
        timeseries[outputKey] = [val];
      }
    }
  }

  // GDP growth rate
  if ('gdp' in timeseries && timeseries['gdp'].length > 1) {
    const gdp = timeseries['gdp'];
    const growth: number[] = [];
    for (let i = 1; i < gdp.length; i++) {
      growth.push(gdp[i - 1] !== 0 ? ((gdp[i] - gdp[i - 1]) / gdp[i - 1]) * 100 : 0.0);
    }
    timeseries['gdp_growth_rate'] = growth;
  }

  // GDP per capita (derived)
  if (!('gdp_per_capita' in timeseries) && 'gdp' in timeseries && 'population' in timeseries) {
    const gdp = timeseries['gdp'];
    const pop = timeseries['population'];
    const minLen = Math.min(gdp.length, pop.length);
    timeseries['gdp_per_capita'] = Array.from({ length: minLen }, (_, i) =>
      pop[i] !== 0 ? gdp[i] / pop[i] : 0,
    );
  }

  return timeseries;
}

// ─── Snapshot extraction ──────────────────────────────────────────────────

function extractSnapshot(
  _gamestate: ParsedData,
  countryData: ParsedData,
  _countryId: CountryId,
): SnapshotData {
  const snapshot: Record<string, number | undefined> = {};
  if (!isRecord(countryData)) return snapshot;

  for (const key of [
    'gdp', 'population', 'prestige', 'money', 'literacy',
    'country_type', 'government', 'ruling_interest_groups', 'tax_level',
  ]) {
    if (key in countryData) {
      const val = countryData[key];
      if (isNumber(val)) snapshot[key] = val;
    }
  }

  if ('budget' in countryData) {
    const budget = countryData['budget'];
    if (isRecord(budget)) {
      const rev = budget['revenue'] ?? 0;
      if (isNumber(rev)) snapshot['revenue'] = rev;
      const exp = budget['expense'] ?? budget['expenditure'] ?? 0;
      if (isNumber(exp)) snapshot['expenditure'] = exp;
    }
  }

  if ('military' in countryData) {
    const mil = countryData['military'];
    if (isRecord(mil)) {
      const army = mil['army_size'] ?? 0;
      if (isNumber(army)) snapshot['armySize'] = army;
      const navy = mil['navy_size'] ?? 0;
      if (isNumber(navy)) snapshot['navySize'] = navy;
    }
  }

  if ('technology' in countryData) {
    const tech = countryData['technology'];
    if (isRecord(tech)) {
      const acquired = tech['acquired_technologies'];
      if (Array.isArray(acquired)) snapshot['techCount'] = acquired.length;
    }
  }

  return snapshot;
}

// ─── States extraction ────────────────────────────────────────────────────

function toTitleCase(s: string): string {
  return s.replace(/\b\w/g, c => c.toUpperCase());
}

function extractStates(
  gamestate: ParsedData,
  countryId: CountryId,
): StateInfo[] {
  const statesList: StateInfo[] = [];
  const sm = gamestate['state_manager'] ?? gamestate['states'];
  if (!isRecord(sm)) return statesList;

  const dbRaw = sm['database'] !== undefined ? sm['database'] : sm;
  if (!isRecord(dbRaw)) return statesList;

  for (const [sid, sdata] of Object.entries(dbRaw)) {
    if (!isRecord(sdata)) continue;
    const owner = sdata['country'] ?? sdata['owner'];
    if (!idsEqual(owner as CountryId, countryId)) continue;

    const raw = sdata['region'] ?? sdata['definition'] ?? sdata['name'] ?? sid;
    const display = toTitleCase(
      String(raw).toLowerCase().replace(/state_/g, '').replace(/_/g, ' '),
    );

    const pop = isNumber(sdata['population']) ? (sdata['population'] as number) : 0;
    const gdp = isNumber(sdata['gdp']) ? (sdata['gdp'] as number) : 0;
    const infra = isNumber(sdata['infrastructure']) ? (sdata['infrastructure'] as number) : 0;

    // Build with extra `id` then push (structural typing allows extras)
    const entry = {
      id: sid,
      name: display,
      population: pop,
      populationFmt: '',
      gdp,
      gdpFmt: '',
      infrastructure: infra,
    };
    statesList.push(entry);
  }
  return statesList;
}

// ─── Technology extraction ────────────────────────────────────────────────

function extractTechnology(countryData: ParsedData): TechInfo {
  if (!isRecord(countryData)) return { acquired: [], researching: '' };
  const tech = countryData['technology'];
  if (!isRecord(tech)) return { acquired: [], researching: '' };
  let acquired = tech['acquired_technologies'];
  if (!Array.isArray(acquired)) acquired = [];
  const researching = tech['researching'] ?? '';
  return {
    acquired: (acquired as ParsedValue[]).map(v => String(v)),
    researching: String(researching),
  };
}

// ─── Goods production extraction ──────────────────────────────────────────

function extractGoodsProduction(
  gamestate: ParsedData,
  _countryId: CountryId,
): GoodsInfo[] {
  const goods: GoodsInfo[] = [];
  const mm = gamestate['market_manager'];
  if (!isRecord(mm)) return goods;

  const db = mm['database'];
  if (!isRecord(db)) return goods;

  for (const mdata of Object.values(db)) {
    if (!isRecord(mdata)) continue;
    const goodsData = mdata['goods'];
    if (!isRecord(goodsData)) continue;

    for (const [gname, ginfo] of Object.entries(goodsData)) {
      if (!isRecord(ginfo)) continue;
      const produced = ginfo['produced'] ?? ginfo['supply'] ?? 0;
      const consumed = ginfo['consumed'] ?? ginfo['demand'] ?? 0;
      goods.push({
        name: String(gname),
        production: isNumber(produced) ? produced : 0,
        consumption: isNumber(consumed) ? consumed : 0,
        price: isNumber(ginfo['price']) ? (ginfo['price'] as number) : 0,
      });
    }
  }

  goods.sort((a, b) => b.production - a.production);
  return goods.slice(0, 20);
}

// ─── Subject map extraction ──────────────────────────────────────────────

function extractSubjectMap(gamestate: ParsedData): Record<string, string> {
  const countriesDb = getCountriesDb(gamestate);
  const idToTag: Record<string, string> = {};

  for (const [cid, cdata] of Object.entries(countriesDb)) {
    if (isRecord(cdata)) {
      const tag = String(cdata['definition'] ?? cdata['tag'] ?? cid);
      idToTag[cid] = tag;
    }
  }

  const subjectMap: Record<string, string> = {};

  for (const [cid, cdata] of Object.entries(countriesDb)) {
    if (!isRecord(cdata)) continue;
    if (!('overlord' in cdata)) continue;
    const overlord = cdata['overlord'];

    let overlordId: string;
    if (isRecord(overlord)) {
      const raw = overlord['country'] ?? overlord['id'];
      if (raw === undefined) continue;
      overlordId = String(raw);
    } else {
      overlordId = String(overlord);
    }

    const subjectTag = idToTag[cid] ?? cid;
    const overlordTag = idToTag[overlordId] ?? overlordId;

    if (subjectTag && overlordTag && subjectTag !== overlordTag) {
      subjectMap[subjectTag] = overlordTag;
    }
  }

  return subjectMap;
}

// ─── Territory map extraction ─────────────────────────────────────────────

interface CountryMeta {
  name: string;
  prestige: number;
  armySize: number;
  navySize: number;
  rank: string;
  techCount: number;
}

interface TerritoryEntry {
  tag: string;
  name: string;
  isPlayer: boolean;
  prestige: number;
  gdp: number;
  population: number;
  armySize: number;
  navySize: number;
  rank: string;
  techCount: number;
  numStates: number;
  states: Array<{
    name: string;
    stateKey: string;
    population: number;
    gdp: number;
    infrastructure: number;
  }>;
}

function extractTerritoryMap(gamestate: ParsedData, playerTag: string): TerritoryMap {
  const countriesDb = getCountriesDb(gamestate);
  const idToInfo: Record<string, string> = {};
  const tagToMeta: Record<string, CountryMeta> = {};

  for (const [cid, cdata] of Object.entries(countriesDb)) {
    if (!isRecord(cdata)) continue;
    const tag = String(cdata['definition'] ?? cdata['tag'] ?? cid);
    idToInfo[cid] = tag;

    const name = getCountryName(cdata, tag);

    const prestigeRaw = cdata['prestige'] ?? 0;
    let prestige: number;
    if (isRecord(prestigeRaw)) {
      const vals = extractChannelValues(prestigeRaw);
      const last = vals.length > 0 ? vals[vals.length - 1] : 0;
      prestige = isNumber(last) ? last : 0;
    } else if (isNumber(prestigeRaw)) {
      prestige = prestigeRaw;
    } else {
      prestige = 0;
    }

    const mil = cdata['military'];
    const armyRaw = isRecord(mil) ? (mil['army_size'] ?? 0) : 0;
    const navyRaw = isRecord(mil) ? (mil['navy_size'] ?? 0) : 0;

    let techCount = 0;
    const tech = cdata['technology'];
    if (isRecord(tech)) {
      const acquired = tech['acquired_technologies'];
      if (Array.isArray(acquired)) techCount = acquired.length;
    }

    const rank = cdata['country_rank'] ?? cdata['rank'] ?? '';

    tagToMeta[tag] = {
      name,
      prestige,
      armySize: isNumber(armyRaw) ? armyRaw : 0,
      navySize: isNumber(navyRaw) ? navyRaw : 0,
      rank: String(rank),
      techCount: techCount,
    };
  }

  const subjectMap = extractSubjectMap(gamestate);
  const territories: Record<string, TerritoryEntry> = {};

  const sm = gamestate['state_manager'] ?? gamestate['states'];
  if (isRecord(sm)) {
    const dbRaw = sm['database'] !== undefined ? sm['database'] : sm;
    if (isRecord(dbRaw)) {
      for (const [sid, sdata] of Object.entries(dbRaw)) {
        if (!isRecord(sdata)) continue;
        const owner = sdata['country'] ?? sdata['owner'];
        const tag = idToInfo[String(owner)] ?? String(owner);

        const rawName = String(
          sdata['region'] ?? sdata['definition'] ?? sdata['name'] ?? sid,
        );
        let stateKey = rawName.toUpperCase();
        if (!stateKey.startsWith('STATE_')) stateKey = 'STATE_' + stateKey;
        const display = toTitleCase(
          rawName.toLowerCase().replace(/state_/g, '').replace(/_/g, ' '),
        );

        let pop: number = isNumber(sdata['population'])
          ? (sdata['population'] as number) : 0;
        let gdp: number = isNumber(sdata['gdp'])
          ? (sdata['gdp'] as number) : 0;
        const infra: number = isNumber(sdata['infrastructure'])
          ? (sdata['infrastructure'] as number) : 0;

        if (!isNumber(pop)) pop = 0;
        if (!isNumber(gdp)) gdp = 0;

        if (!(tag in territories)) {
          const meta = tagToMeta[tag] ?? {
            name: tag, prestige: 0, armySize: 0, navySize: 0, rank: '', techCount: 0,
          };
          territories[tag] = {
            tag,
            name: meta.name,
            isPlayer: tag === playerTag,
            prestige: meta.prestige,
            gdp: 0,
            population: 0,
            armySize: meta.armySize,
            navySize: meta.navySize,
            rank: meta.rank,
            techCount: meta.techCount,
            numStates: 0,
            states: [],
          };
        }

        const stateEntry = {
          name: display,
          stateKey,
          population: pop,
          gdp,
          infrastructure: infra,
        };
        territories[tag].states.push(stateEntry);
        territories[tag].population += pop;
        territories[tag].gdp += gdp;
      }
    }
  }

  const countryList = Object.values(territories);
  countryList.sort((a, b) => {
    if (a.prestige !== b.prestige) return b.prestige - a.prestige;
    return b.gdp - a.gdp;
  });

  for (const c of countryList) {
    c.numStates = c.states.length;
    c.states.sort((a, b) => b.population - a.population);
  }

  return {
    playerTag,
    countries: countryList,
    subjectMap,
  };
}

// ─── Country comparison extraction ────────────────────────────────────────

function extractAllCountries(
  gamestate: ParsedData,
  playerId: CountryId,
  selectedTags?: boolean | string[],
): ComparisonCountry[] {
  const countriesDb = getCountriesDb(gamestate);

  let countryHistory: ParsedValue = gamestate['country_history'] ?? {};
  if (isRecord(countryHistory) && 'database' in countryHistory)
    countryHistory = countryHistory['database'] ?? {};

  let tagFilter: Set<string> | null = null;
  if (Array.isArray(selectedTags) && selectedTags.length > 0) {
    tagFilter = new Set(selectedTags.map(t => String(t)));
  }

  const countries: ComparisonCountry[] = [];

  // Strategy 1: dedicated country_history section
  if (isRecord(countryHistory) && Object.keys(countryHistory).length > 0) {
    for (const [cidKey, history] of Object.entries(countryHistory)) {
      if (!isRecord(history)) continue;
      const rawCd = countriesDb[cidKey];
      const cd = isRecord(rawCd) ? rawCd : ({} as ParsedData);
      const tag = String(cd['definition'] ?? cidKey);
      if (tagFilter && !tagFilter.has(tag)) continue;
      const ts = extractTimeseries(history);
      if (!ts || !('gdp' in ts)) continue;
      const name = getCountryName(cd, tag);
      const isPlayer = idsEqual(cidKey, playerId);
      countries.push({ tag, name, isPlayer, timeseries: ts });
    }
  }

  // Strategy 2: history embedded in country entries (melted binary saves)
  if (countries.length === 0) {
    for (const [cidKey, countryData] of Object.entries(countriesDb)) {
      if (!isRecord(countryData)) continue;
      const tag = String(countryData['definition'] ?? cidKey);
      if (tagFilter && !tagFilter.has(tag)) continue;
      const history = extractEmbeddedHistory(countryData);
      if (Object.keys(history).length === 0) continue;
      const ts = extractTimeseries(history);
      if (!ts || !('gdp' in ts)) continue;
      const name = getCountryName(countryData, tag);
      const isPlayer = idsEqual(cidKey, playerId);
      countries.push({ tag, name, isPlayer, timeseries: ts });
    }
  }

  countries.sort((a, b) => {
    if (a.isPlayer !== b.isPlayer) return a.isPlayer ? -1 : 1;
    const aGdp = a.timeseries.gdp ?? [0];
    const bGdp = b.timeseries.gdp ?? [0];
    return bGdp[bGdp.length - 1] - aGdp[aGdp.length - 1];
  });

  return countries;
}

// ─── Public API ───────────────────────────────────────────────────────────

/** Extract all available metrics from a parsed save. */
export function extractAll(
  gamestate: ParsedData,
  meta: ParsedData,
  compareCountries: boolean | string[] = false,
): ExtractedData {
  const playerTag = getPlayerTag(meta, gamestate);
  const playerId = findCountryId(gamestate, playerTag);
  const gameDate = getGameDate(meta, gamestate);

  const countryData = getCountry(gamestate, playerId);
  const history = getCountryHistory(gamestate, playerId);

  const result: ExtractedData = {
    meta: {
      playerTag,
      playerId: playerId ?? 0,
      gameDate,
      countryName: getCountryName(countryData, playerTag),
    },
    timeseries: extractTimeseries(history),
    snapshot: extractSnapshot(gamestate, countryData, playerId),
    states: extractStates(gamestate, playerId),
    technology: extractTechnology(countryData),
    goods: extractGoodsProduction(gamestate, playerId),
    territoryMap: extractTerritoryMap(gamestate, playerTag),
  };

  if (compareCountries) {
    const countries = extractAllCountries(gamestate, playerId, compareCountries);
    // Transform per-country comparison into flat format expected by ExtractedData
    const compTimeseries: TimeseriesData = {};
    const tags: string[] = [];
    const names: Record<string, string> = {};
    for (const c of countries) {
      tags.push(c.tag);
      names[c.tag] = c.name;
      for (const [metric, values] of Object.entries(c.timeseries)) {
        compTimeseries[`${c.tag}:${metric}`] = values;
      }
    }
    result.comparison = { timeseries: compTimeseries, tags, names };
  }

  return result;
}

/** Return a list of all countries with history data. */
export function listCountries(
  gamestate: ParsedData,
  meta: ParsedData,
): CountryListItem[] {
  const playerTag = getPlayerTag(meta, gamestate);
  const playerId = findCountryId(gamestate, playerTag);
  const countriesDb = getCountriesDb(gamestate);

  let countryHistory: ParsedValue = gamestate['country_history'] ?? {};
  if (isRecord(countryHistory) && 'database' in countryHistory)
    countryHistory = countryHistory['database'] ?? {};

  const results: CountryListItem[] = [];

  // Strategy 1: dedicated country_history section
  if (isRecord(countryHistory) && Object.keys(countryHistory).length > 0) {
    for (const [cidKey, history] of Object.entries(countryHistory)) {
      if (!isRecord(history)) continue;
      const gdpData = history['weekly_gdp'] ?? history['gdp'];
      if (!Array.isArray(gdpData) || gdpData.length < 2) continue;
      const rawCd = countriesDb[cidKey];
      const countryData = isRecord(rawCd) ? rawCd : ({} as ParsedData);
      const tag = String(countryData['definition'] ?? cidKey);
      const name = getCountryName(countryData, tag);
      const isPlayer = idsEqual(cidKey, playerId);
      const finalGdp = gdpData.length > 0 ? gdpData[gdpData.length - 1] : 0;
      results.push({
        tag,
        name,
        isPlayer,
        finalGdp: isNumber(finalGdp) ? finalGdp : 0,
      });
    }
  }

  // Strategy 2: history embedded in country entries (melted binary saves)
  if (results.length === 0) {
    for (const [cidKey, countryData] of Object.entries(countriesDb)) {
      if (!isRecord(countryData)) continue;
      const gdpBlock = countryData['gdp'];
      if (!isRecord(gdpBlock) || !('channels' in gdpBlock)) continue;
      const gdpVals = extractChannelValues(gdpBlock);
      if (gdpVals.length < 2) continue;
      const tag = String(countryData['definition'] ?? cidKey);
      const name = getCountryName(countryData, tag);
      const isPlayer = idsEqual(cidKey, playerId);
      const finalGdp = gdpVals.length > 0 ? gdpVals[gdpVals.length - 1] : 0;
      results.push({
        tag,
        name,
        isPlayer,
        finalGdp: isNumber(finalGdp) ? finalGdp : 0,
      });
    }
  }

  results.sort((a, b) => {
    if (a.isPlayer !== b.isPlayer) return a.isPlayer ? -1 : 1;
    return b.finalGdp - a.finalGdp;
  });

  return results;
}
