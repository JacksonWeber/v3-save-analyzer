/** Shared types for the V3 Save Analyzer. */

export interface ParsedData {
  [key: string]: ParsedValue;
}

export type ParsedValue =
  | string
  | number
  | boolean
  | ParsedData
  | ParsedValue[];

export interface RawSave {
  gamestate: string;
  meta: string;
}

export interface MetaInfo {
  playerTag: string;
  playerId: string | number;
  gameDate: string;
  countryName: string;
}

export interface TimeseriesData {
  [key: string]: number[];
}

export interface CardData {
  label: string;
  value: string;
}

export interface ChartDataset {
  label: string;
  data: number[];
  borderColor?: string;
  backgroundColor?: string;
  borderWidth?: number;
  tension?: number;
  pointRadius?: number;
}

export interface ChartConfig {
  title: string;
  labels: string[];
  datasets: ChartDataset[];
}

export interface StateInfo {
  name: string;
  population: number;
  populationFmt: string;
  gdp: number;
  gdpFmt: string;
  infrastructure: number;
}

export interface TechInfo {
  acquired: string[];
  researching: string;
}

export interface GoodsInfo {
  name: string;
  production: number;
  consumption: number;
  price: number;
}

export interface SnapshotData {
  gdp?: number;
  population?: number;
  treasury?: number;
  standardOfLiving?: number;
  literacy?: number;
  prestige?: number;
  revenue?: number;
  expense?: number;
  armySize?: number;
  navySize?: number;
  numStates?: number;
  techCount?: number;
  [key: string]: number | undefined;
}

export interface TerritoryCountry {
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
  states: { name: string; stateKey: string; population: number; gdp: number; infrastructure: number }[];
}

export interface TerritoryMap {
  playerTag: string;
  countries: TerritoryCountry[];
  subjectMap: Record<string, string>;
}

export interface TopCountry {
  rank: number;
  tag: string;
  name: string;
  isPlayer: boolean;
  prestige: number;
  gdp: number;
  population: number;
  armySize: number;
  navySize: number;
  numStates: number;
}

export interface ExtractedData {
  meta: MetaInfo;
  timeseries: TimeseriesData;
  snapshot: SnapshotData;
  states: StateInfo[];
  technology: TechInfo;
  goods: GoodsInfo[];
  territoryMap: TerritoryMap;
  comparison?: {
    timeseries: TimeseriesData;
    tags: string[];
    names: Record<string, string>;
  };
}

export interface CountryListItem {
  tag: string;
  name: string;
  isPlayer: boolean;
  finalGdp: number;
}

export interface DashboardData {
  meta: MetaInfo;
  cards: CardData[];
  charts: ChartConfig[];
  comparisonCharts: ChartConfig[];
  showPlayerDetails: boolean;
  states: StateInfo[];
  technology: TechInfo;
  goods: GoodsInfo[];
  territoryMap: TerritoryMap;
  topCountries: TopCountry[];
}
