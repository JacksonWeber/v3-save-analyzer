/**
 * Army Composition Optimizer for Victoria 3.
 * Standalone tool — no save-file data required.
 */

// ---------------------------------------------------------------------------
// Data types
// ---------------------------------------------------------------------------

interface Unit {
  id: string;
  name: string;
  group: 'infantry' | 'artillery' | 'cavalry';
  offense: number;
  defense: number;
  moraleLoss: number;
  killRate: number;
  moraleDamage: number;
  devastation: number;
  occupation: number;
  tech: string | null;
  upkeep: Array<{ good: string; qty: number }>;
  speed: number;
  moraleLossMult?: number;
}

interface Technology {
  id: string;
  name: string;
  era: number;
}

interface VeterancyLevel {
  level: number;
  name: string;
  offenseMult: number;
  defenseMult: number;
  moraleDamageMult: number;
}

interface Trait {
  id: string;
  name: string;
  category: 'skill' | 'personality' | 'condition';
  mods: Record<string, number>;
}

interface Order {
  id: string;
  name: string;
  mods: Record<string, number>;
  requires: string | null;
}

interface EffectiveStats {
  offense: number;
  defense: number;
  moraleLoss: number;
  killRate: number;
  moraleDamage: number;
  devastation: number;
  occupation: number;
  speed: number;
}

// ---------------------------------------------------------------------------
// Game data constants
// ---------------------------------------------------------------------------

const UNITS: Unit[] = [
  // INFANTRY
  { id: 'irregular_infantry', name: 'Irregular Infantry', group: 'infantry', offense: 10, defense: 10, moraleLoss: 15, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0, tech: null, upkeep: [], speed: 0 },
  { id: 'line_infantry', name: 'Line Infantry', group: 'infantry', offense: 20, defense: 25, moraleLoss: 10, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0, tech: 'line_infantry', upkeep: [{ good: 'small_arms', qty: 1 }], speed: 0 },
  { id: 'skirmish_infantry', name: 'Skirmish Infantry', group: 'infantry', offense: 25, defense: 35, moraleLoss: 10, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0, tech: 'general_staff', upkeep: [{ good: 'small_arms', qty: 2 }, { good: 'ammunition', qty: 1 }], speed: 0 },
  { id: 'trench_infantry', name: 'Trench Infantry', group: 'infantry', offense: 30, defense: 40, moraleLoss: 8, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0, tech: 'trench_works', upkeep: [{ good: 'small_arms', qty: 3 }, { good: 'ammunition', qty: 2 }], speed: 0 },
  { id: 'squad_infantry', name: 'Squad Infantry', group: 'infantry', offense: 40, defense: 50, moraleLoss: 6, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0, tech: 'nco_training', upkeep: [{ good: 'small_arms', qty: 3 }, { good: 'ammunition', qty: 3 }, { good: 'radios', qty: 1 }], speed: 0 },
  { id: 'mechanized_infantry', name: 'Mechanized Infantry', group: 'infantry', offense: 50, defense: 60, moraleLoss: 4, killRate: 0, moraleDamage: 0, devastation: 0.1, occupation: 0, tech: 'mobile_armor', upkeep: [{ good: 'small_arms', qty: 3 }, { good: 'ammunition', qty: 3 }, { good: 'oil', qty: 1 }, { good: 'radios', qty: 1 }, { good: 'tanks', qty: 1 }], speed: 0 },
  // ARTILLERY
  { id: 'cannon_artillery', name: 'Cannon Artillery', group: 'artillery', offense: 25, defense: 15, moraleLoss: 10, killRate: 0.1, moraleDamage: 0, devastation: 0.1, occupation: 0, tech: 'artillery', upkeep: [{ good: 'artillery', qty: 1 }], speed: -0.2 },
  { id: 'mobile_artillery', name: 'Mobile Artillery', group: 'artillery', offense: 30, defense: 15, moraleLoss: 8, killRate: 0.2, moraleDamage: 0, devastation: 0.15, occupation: 0, tech: 'napoleonic_warfare', upkeep: [{ good: 'artillery', qty: 2 }], speed: -0.2 },
  { id: 'shrapnel_artillery', name: 'Shrapnel Artillery', group: 'artillery', offense: 45, defense: 25, moraleLoss: 6, killRate: 0.3, moraleDamage: 0, devastation: 0.15, occupation: 0, tech: 'breech_loading_artillery', upkeep: [{ good: 'artillery', qty: 3 }, { good: 'ammunition', qty: 3 }], speed: -0.2 },
  { id: 'siege_artillery', name: 'Siege Artillery', group: 'artillery', offense: 55, defense: 30, moraleLoss: 6, killRate: 0.25, moraleDamage: 0, devastation: 0.2, occupation: 0, tech: 'defense_in_depth', upkeep: [{ good: 'artillery', qty: 4 }, { good: 'ammunition', qty: 4 }, { good: 'radios', qty: 1 }], speed: -0.2 },
  { id: 'heavy_tank', name: 'Heavy Tank', group: 'artillery', offense: 70, defense: 35, moraleLoss: 4, killRate: 0.25, moraleDamage: 0.15, devastation: 0.2, occupation: 0, tech: 'mobile_armor', upkeep: [{ good: 'tanks', qty: 3 }, { good: 'artillery', qty: 4 }, { good: 'ammunition', qty: 4 }, { good: 'radios', qty: 1 }, { good: 'oil', qty: 3 }], speed: -0.2 },
  // CAVALRY
  { id: 'hussars', name: 'Hussars', group: 'cavalry', offense: 15, defense: 10, moraleLoss: 10, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0, tech: 'standing_army', upkeep: [{ good: 'grain', qty: 1 }], speed: 0.25 },
  { id: 'dragoons', name: 'Dragoons', group: 'cavalry', offense: 20, defense: 25, moraleLoss: 8, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0.3, tech: 'line_infantry', upkeep: [{ good: 'grain', qty: 1 }, { good: 'small_arms', qty: 2 }], speed: 0 },
  { id: 'cuirassiers', name: 'Cuirassiers', group: 'cavalry', offense: 25, defense: 20, moraleLoss: 8, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0.3, tech: 'line_infantry', upkeep: [{ good: 'grain', qty: 1 }, { good: 'small_arms', qty: 2 }], speed: 0 },
  { id: 'lancers', name: 'Lancers', group: 'cavalry', offense: 30, defense: 20, moraleLoss: 6, killRate: 0.05, moraleDamage: 0, devastation: 0, occupation: 0.3, tech: 'napoleonic_warfare', upkeep: [{ good: 'grain', qty: 2 }, { good: 'small_arms', qty: 2 }, { good: 'iron', qty: 2 }], speed: 0, moraleLossMult: 0.05 },
  { id: 'light_tanks', name: 'Light Tanks', group: 'cavalry', offense: 45, defense: 45, moraleLoss: 4, killRate: 0, moraleDamage: 0, devastation: 0.1, occupation: 0.3, tech: 'mobile_armor', upkeep: [{ good: 'tanks', qty: 2 }, { good: 'artillery', qty: 2 }, { good: 'oil', qty: 2 }, { good: 'ammunition', qty: 2 }, { good: 'radios', qty: 2 }], speed: 0.2 },
];

const TECHNOLOGIES: Technology[] = [
  { id: 'standing_army', name: 'Standing Army', era: 1 },
  { id: 'line_infantry', name: 'Line Infantry', era: 1 },
  { id: 'artillery', name: 'Artillery', era: 1 },
  { id: 'napoleonic_warfare', name: 'Napoleonic Warfare', era: 1 },
  { id: 'general_staff', name: 'General Staff', era: 2 },
  { id: 'breech_loading_artillery', name: 'Breech-Loading Artillery', era: 3 },
  { id: 'trench_works', name: 'Trench Works', era: 4 },
  { id: 'defense_in_depth', name: 'Defense in Depth', era: 4 },
  { id: 'nco_training', name: 'NCO Training', era: 5 },
  { id: 'mobile_armor', name: 'Mobile Armor', era: 5 },
];

const UPGRADES: Record<string, string[]> = {
  irregular_infantry: ['line_infantry', 'skirmish_infantry', 'trench_infantry', 'squad_infantry', 'mechanized_infantry'],
  line_infantry: ['skirmish_infantry', 'trench_infantry', 'squad_infantry', 'mechanized_infantry'],
  skirmish_infantry: ['trench_infantry', 'squad_infantry', 'mechanized_infantry'],
  trench_infantry: ['squad_infantry', 'mechanized_infantry'],
  squad_infantry: ['mechanized_infantry'],
  cannon_artillery: ['mobile_artillery', 'shrapnel_artillery', 'siege_artillery'],
  mobile_artillery: ['shrapnel_artillery', 'siege_artillery'],
  shrapnel_artillery: ['siege_artillery'],
  hussars: ['dragoons', 'cuirassiers', 'lancers'],
};

const VETERANCY: VeterancyLevel[] = [
  { level: 0, name: 'No Veterancy', offenseMult: 0, defenseMult: 0, moraleDamageMult: 0 },
  { level: 1, name: 'Veterancy I', offenseMult: 0.05, defenseMult: 0.05, moraleDamageMult: 0 },
  { level: 2, name: 'Veterancy II', offenseMult: 0.10, defenseMult: 0.10, moraleDamageMult: 0 },
  { level: 3, name: 'Veterancy III', offenseMult: 0.15, defenseMult: 0.15, moraleDamageMult: 0.25 },
  { level: 4, name: 'Veterancy IV', offenseMult: 0.25, defenseMult: 0.25, moraleDamageMult: 0.5 },
];

const TRAITS: Trait[] = [
  // ---- SKILL (15) ----
  { id: 'basic_offensive_planner', name: 'Basic Offensive Planner', category: 'skill', mods: { unit_offense_mult: 0.05 } },
  { id: 'experienced_offensive_planner', name: 'Experienced Offensive Planner', category: 'skill', mods: { unit_offense_mult: 0.10 } },
  { id: 'expert_offensive_planner', name: 'Expert Offensive Planner', category: 'skill', mods: { unit_offense_mult: 0.20 } },
  { id: 'basic_defensive_strategist', name: 'Basic Defensive Strategist', category: 'skill', mods: { unit_defense_mult: 0.10 } },
  { id: 'experienced_defensive_strategist', name: 'Experienced Defensive Strategist', category: 'skill', mods: { unit_defense_mult: 0.20 } },
  { id: 'expert_defensive_strategist', name: 'Expert Defensive Strategist', category: 'skill', mods: { unit_defense_mult: 0.30 } },
  { id: 'basic_artillery_commander', name: 'Basic Artillery Commander', category: 'skill', mods: { unit_artillery_offense_mult: 0.05 } },
  { id: 'experienced_artillery_commander', name: 'Experienced Artillery Commander', category: 'skill', mods: { unit_artillery_offense_mult: 0.10 } },
  { id: 'expert_artillery_commander', name: 'Expert Artillery Commander', category: 'skill', mods: { unit_artillery_offense_mult: 0.15 } },
  { id: 'stalwart_defender', name: 'Stalwart Defender', category: 'skill', mods: { unit_defense_mult: 0.10 } },
  { id: 'trench_rat', name: 'Trench Rat', category: 'skill', mods: { unit_defense_add: 10 } },
  { id: 'defense_in_depth_specialist', name: 'Defense in Depth Specialist', category: 'skill', mods: { unit_defense_add: 20 } },
  { id: 'bandit', name: 'Bandit', category: 'skill', mods: { unit_morale_damage_mult: 0.10 } },
  { id: 'social_bandit', name: 'Social Bandit', category: 'skill', mods: { unit_morale_damage_mult: 0.10 } },
  { id: 'pillager', name: 'Pillager', category: 'skill', mods: { unit_devastation_mult: 0.25 } },
  { id: 'plains_commander', name: 'Plains Commander', category: 'skill', mods: { unit_offense_mult: 0.25 } },
  { id: 'forest_commander', name: 'Forest Commander', category: 'skill', mods: { unit_defense_mult: 0.25 } },
  { id: 'mountain_commander', name: 'Mountain Commander', category: 'skill', mods: { unit_defense_mult: 0.25 } },
  { id: 'surveyor', name: 'Surveyor', category: 'skill', mods: { unit_offense_mult: 0.10, unit_defense_mult: 0.10 } },
  { id: 'elder', name: 'Elder', category: 'skill', mods: {} },
  { id: 'resupply_commander', name: 'Resupply Commander', category: 'skill', mods: {} },
  { id: 'basic_diplomat', name: 'Basic Diplomat', category: 'skill', mods: { unit_recovery_rate_add: 0.25 } },
  { id: 'experienced_diplomat', name: 'Experienced Diplomat', category: 'skill', mods: { unit_recovery_rate_add: 0.50 } },
  { id: 'masterful_diplomat', name: 'Masterful Diplomat', category: 'skill', mods: { unit_recovery_rate_add: 1.00 } },
  { id: 'inept', name: 'Inept', category: 'skill', mods: { unit_recovery_rate_add: -0.25, unit_offense_mult: -0.10, unit_defense_mult: -0.10 } },
  { id: 'inexperienced', name: 'Inexperienced', category: 'skill', mods: { unit_recovery_rate_add: 0.10, unit_offense_mult: -0.05, unit_defense_mult: -0.05 } },
  // ---- PERSONALITY (18) ----
  { id: 'direct', name: 'Direct', category: 'personality', mods: { unit_offense_mult: 0.10 } },
  { id: 'persistent', name: 'Persistent', category: 'personality', mods: { unit_morale_loss_mult: -0.15 } },
  { id: 'innovative', name: 'Innovative', category: 'personality', mods: { unit_morale_loss_mult: -0.15 } },
  { id: 'cautious', name: 'Cautious', category: 'personality', mods: { unit_morale_loss_mult: -0.05 } },
  { id: 'brave', name: 'Brave', category: 'personality', mods: { unit_morale_loss_mult: -0.10 } },
  { id: 'imposing', name: 'Imposing', category: 'personality', mods: { unit_morale_loss_mult: -0.10 } },
  { id: 'reserved', name: 'Reserved', category: 'personality', mods: { unit_morale_loss_mult: -0.05 } },
  { id: 'meticulous', name: 'Meticulous', category: 'personality', mods: { unit_offense_mult: 0.05, unit_defense_mult: 0.05, unit_recovery_rate_add: 0.10 } },
  { id: 'charismatic', name: 'Charismatic', category: 'personality', mods: { unit_recovery_rate_add: 0.10 } },
  { id: 'tactful', name: 'Tactful', category: 'personality', mods: { unit_defense_add: 5, unit_morale_damage_mult: -0.05 } },
  { id: 'cruel', name: 'Cruel', category: 'personality', mods: { unit_kill_rate_add: 0.10 } },
  { id: 'wrathful', name: 'Wrathful', category: 'personality', mods: { unit_morale_loss_mult: 0.05, unit_morale_damage_mult: 0.10 } },
  { id: 'ambitious', name: 'Ambitious', category: 'personality', mods: { unit_offense_mult: 0.05, unit_recovery_rate_add: -0.05 } },
  { id: 'bigoted', name: 'Bigoted', category: 'personality', mods: { unit_offense_mult: 0.05, unit_morale_loss_mult: 0.05 } },
  { id: 'romantic', name: 'Romantic', category: 'personality', mods: { unit_morale_loss_mult: -0.10, unit_offense_mult: -0.10 } },
  { id: 'pious', name: 'Pious', category: 'personality', mods: { unit_kill_rate_add: -0.10, unit_morale_loss_mult: -0.25, unit_recovery_rate_add: 0.25 } },
  { id: 'imperious', name: 'Imperious', category: 'personality', mods: { unit_morale_loss_mult: -0.15, unit_recovery_rate_add: -0.15 } },
  { id: 'reckless', name: 'Reckless', category: 'personality', mods: { unit_recovery_rate_add: -0.10 } },
  { id: 'hedonist', name: 'Hedonist', category: 'personality', mods: { unit_supply_consumption_mult: 0.10, unit_recovery_rate_add: 0.05 } },
  // ---- CONDITIONS (7) ----
  { id: 'alcoholic', name: 'Alcoholic', category: 'condition', mods: { unit_morale_damage_mult: -0.10 } },
  { id: 'shellshocked', name: 'Shellshocked', category: 'condition', mods: { unit_morale_loss_mult: 0.20, unit_offense_mult: -0.20, unit_defense_mult: -0.20 } },
  { id: 'war_criminal', name: 'War Criminal', category: 'condition', mods: { unit_kill_rate_add: 0.10 } },
  { id: 'wounded', name: 'Wounded', category: 'condition', mods: { unit_morale_loss_mult: 0.10 } },
  { id: 'senile', name: 'Senile', category: 'condition', mods: { unit_morale_loss_mult: 0.10 } },
  { id: 'kidney_stones', name: 'Kidney Stones', category: 'condition', mods: { unit_offense_mult: -0.10, unit_defense_mult: -0.10 } },
  { id: 'grifter', name: 'Grifter', category: 'condition', mods: { unit_supply_consumption_mult: 0.05 } },
];

const ORDERS: Order[] = [
  { id: 'advance', name: 'Advance', mods: { unit_offense_mult: 0.1 }, requires: null },
  { id: 'advance_reckless', name: 'Advance (Reckless)', mods: { unit_offense_mult: 0.15, unit_morale_loss_mult: 0.1, unit_recovery_rate_add: -0.1 }, requires: 'reckless' },
  { id: 'advance_pillager', name: 'Advance (Pillage)', mods: { unit_kill_rate_add: 0.3, unit_devastation_mult: 1, unit_morale_damage_mult: 0.2 }, requires: 'cruel|wrathful|pillager' },
  { id: 'advance_cautious', name: 'Advance (Cautious)', mods: { unit_morale_loss_mult: -0.05, unit_recovery_rate_add: 0.1 }, requires: 'cautious' },
  { id: 'advance_heavy_barrage', name: 'Advance (Heavy Barrage)', mods: { unit_devastation_mult: 0.75, unit_kill_rate_add: 0.25, unit_morale_damage_mult: 0.15 }, requires: 'basic_artillery_commander|experienced_artillery_commander|expert_artillery_commander' },
  { id: 'advance_cavalry_assault', name: 'Advance (Cavalry Assault)', mods: { unit_morale_damage_mult: 0.1, unit_offense_mult: 0.1 }, requires: null },
  { id: 'advance_tank_assault', name: 'Advance (Tank Assault)', mods: { unit_morale_loss_mult: -0.05, unit_offense_mult: 0.15 }, requires: 'innovative' },
  { id: 'defend', name: 'Defend', mods: { unit_defense_mult: 0.1 }, requires: null },
  { id: 'defend_dig_in', name: 'Defend (Dig In)', mods: { unit_defense_mult: 0.15, unit_supply_consumption_mult: 0.2 }, requires: 'basic_defensive_strategist|experienced_defensive_strategist|expert_defensive_strategist' },
  { id: 'defend_desperate_charge', name: 'Defend (Desperate Charge)', mods: { unit_kill_rate_add: 0.25, unit_morale_damage_mult: 0.15 }, requires: 'brave' },
  { id: 'defend_last_stand', name: 'Defend (Last Stand)', mods: { unit_defense_mult: 0.2 }, requires: 'stalwart_defender|trench_rat|defense_in_depth_specialist' },
  { id: 'defend_guerilla', name: 'Defend (Guerrilla)', mods: { unit_defense_mult: 0.1, unit_morale_loss_mult: 0.25 }, requires: 'pillager|cruel|wrathful|bandit|social_bandit' },
];

const GROUP_COLORS: Record<string, string> = {
  infantry: '#2ecc71',
  artillery: '#e67e22',
  cavalry: '#4a90d9',
};

// ---------------------------------------------------------------------------
// Stat computation
// ---------------------------------------------------------------------------

function computeStats(unit: Unit, mods: Record<string, number>, vetLevel: number): EffectiveStats {
  const vet = VETERANCY[vetLevel];
  const offAdd = mods.unit_offense_add ?? 0;
  const defAdd = mods.unit_defense_add ?? 0;
  const killAdd = mods.unit_kill_rate_add ?? 0;
  let offMult = (mods.unit_offense_mult ?? 0) + vet.offenseMult;
  let defMult = (mods.unit_defense_mult ?? 0) + vet.defenseMult;
  let moraleMult = mods.unit_morale_loss_mult ?? 0;
  const moraleDmgMult = (mods.unit_morale_damage_mult ?? 0) + vet.moraleDamageMult;
  const devMult = mods.unit_devastation_mult ?? 0;

  if (unit.group === 'artillery') {
    offMult += mods.unit_artillery_offense_mult ?? 0;
  }
  if (unit.moraleLossMult) moraleMult += unit.moraleLossMult;

  return {
    offense: (unit.offense + offAdd) * (1 + offMult),
    defense: (unit.defense + defAdd) * (1 + defMult),
    moraleLoss: unit.moraleLoss * (1 + moraleMult),
    killRate: unit.killRate + killAdd,
    moraleDamage: unit.moraleDamage + moraleDmgMult,
    devastation: unit.devastation + devMult,
    occupation: unit.occupation,
    speed: unit.speed,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtNum(n: number, dec = 1): string {
  return Number.isInteger(n) ? n.toString() : n.toFixed(dec);
}

function fmtPct(n: number): string {
  return (n * 100).toFixed(0) + '%';
}

function goodName(g: string): string {
  return g.split('_').map(w => w[0].toUpperCase() + w.slice(1)).join(' ');
}

function modLabel(key: string, val: number): string {
  const sign = val > 0 ? '+' : '';
  const labels: Record<string, string> = {
    unit_offense_mult: `${sign}${fmtPct(val)} Offense`,
    unit_offense_add: `${sign}${val} Offense`,
    unit_defense_mult: `${sign}${fmtPct(val)} Defense`,
    unit_defense_add: `${sign}${val} Defense`,
    unit_morale_loss_mult: `${sign}${fmtPct(val)} Morale Loss`,
    unit_kill_rate_add: `${sign}${fmtPct(val)} Kill Rate`,
    unit_morale_damage_mult: `${sign}${fmtPct(val)} Morale Damage`,
    unit_devastation_mult: `${sign}${fmtPct(val)} Devastation`,
    unit_artillery_offense_mult: `${sign}${fmtPct(val)} Artillery Offense`,
    unit_recovery_rate_add: `${sign}${fmtPct(val)} Recovery`,
    unit_supply_consumption_mult: `${sign}${fmtPct(val)} Supply`,
  };
  return labels[key] ?? `${sign}${val} ${key}`;
}

function modSummary(mods: Record<string, number>): string {
  return Object.entries(mods).map(([k, v]) => modLabel(k, v)).join(', ');
}

/** Merge multiple mod objects by summing values */
function mergeMods(...sources: Record<string, number>[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const src of sources) {
    for (const [k, v] of Object.entries(src)) {
      out[k] = (out[k] ?? 0) + v;
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Inject scoped CSS
// ---------------------------------------------------------------------------

function injectStyles(): void {
  if (document.getElementById('army-styles')) return;
  const style = document.createElement('style');
  style.id = 'army-styles';
  style.textContent = `
    .army-layout {
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 24px;
      align-items: start;
    }
    @media (max-width: 900px) {
      .army-layout { grid-template-columns: 1fr; }
    }

    .army-sidebar {
      position: sticky;
      top: 70px;
      max-height: calc(100vh - 80px);
      overflow-y: auto;
      padding-right: 4px;
    }

    .army-sidebar::-webkit-scrollbar { width: 6px; }
    .army-sidebar::-webkit-scrollbar-track { background: transparent; }
    .army-sidebar::-webkit-scrollbar-thumb { background: rgba(60,65,110,0.5); border-radius: 3px; }

    .army-panel {
      background: var(--glass);
      backdrop-filter: blur(10px);
      border: 1px solid var(--glass-border);
      border-radius: var(--radius-md);
      padding: 16px;
      margin-bottom: 16px;
    }

    .army-panel h3 {
      color: var(--gold);
      font-size: 0.9em;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border);
    }

    .era-group { margin-bottom: 10px; }
    .era-label {
      font-size: 0.78em;
      color: var(--text-secondary);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
    }
    .era-btns { display: flex; gap: 4px; margin-bottom: 8px; flex-wrap: wrap; }
    .era-btn {
      background: rgba(15,52,96,0.5);
      color: var(--text-secondary);
      border: 1px solid var(--border);
      padding: 3px 10px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: 0.75em;
      font-weight: 500;
      transition: all var(--transition);
    }
    .era-btn:hover { border-color: var(--gold); color: var(--gold); }

    .check-row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 3px 0;
    }
    .check-row input[type="checkbox"],
    .check-row input[type="radio"] {
      width: 15px;
      height: 15px;
      accent-color: var(--gold);
      cursor: pointer;
      flex-shrink: 0;
    }
    .check-row label {
      font-size: 0.85em;
      cursor: pointer;
      color: var(--text-primary);
      line-height: 1.3;
    }
    .check-row .mod-hint {
      font-size: 0.72em;
      color: var(--text-secondary);
      margin-left: 4px;
    }

    .trait-section {
      margin-bottom: 8px;
    }
    .trait-section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      cursor: pointer;
      padding: 6px 0;
      user-select: none;
    }
    .trait-section-header span {
      font-size: 0.82em;
      font-weight: 600;
      color: var(--text-primary);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .trait-section-header .chevron {
      font-size: 0.7em;
      color: var(--text-secondary);
      transition: transform 0.2s ease;
    }
    .trait-section-header .chevron.open { transform: rotate(90deg); }
    .trait-section-body { padding-left: 4px; }
    .trait-section-body.collapsed { display: none; }

    .order-disabled label { color: var(--text-secondary) !important; opacity: 0.5; }

    .vet-select, .bn-input {
      background: rgba(15,52,96,0.5);
      border: 1px solid var(--border);
      color: var(--text-primary);
      padding: 6px 10px;
      border-radius: var(--radius-sm);
      font-size: 0.9em;
      width: 100%;
    }
    .vet-select:focus, .bn-input:focus {
      outline: none;
      border-color: var(--gold);
      box-shadow: 0 0 0 2px rgba(226,183,85,0.15);
    }

    .unit-group-header td {
      background: rgba(15,52,96,0.4) !important;
      font-weight: 700;
      font-size: 0.85em;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 8px 16px;
    }

    .unit-name-cell {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .unit-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }
    .unit-base {
      display: block;
      font-size: 0.72em;
      color: var(--text-secondary);
    }

    .builder-row td { vertical-align: middle; }
    .bn-count-input {
      background: rgba(15,52,96,0.5);
      border: 1px solid var(--border);
      color: var(--text-primary);
      padding: 4px 8px;
      border-radius: var(--radius-sm);
      font-size: 0.85em;
      width: 60px;
      text-align: center;
    }
    .bn-count-input:focus {
      outline: none;
      border-color: var(--gold);
    }

    .builder-totals td {
      font-weight: 700;
      color: var(--gold);
      border-top: 2px solid var(--border) !important;
    }

    .warning-banner {
      background: rgba(233,69,96,0.1);
      border: 1px solid rgba(233,69,96,0.3);
      border-radius: var(--radius-sm);
      padding: 8px 14px;
      color: var(--accent);
      font-size: 0.85em;
      margin-bottom: 12px;
    }

    .template-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }
    .template-card {
      background: var(--glass);
      backdrop-filter: blur(10px);
      border: 1px solid var(--glass-border);
      border-radius: var(--radius-md);
      padding: 18px 16px;
      transition: all var(--transition);
    }
    .template-card:hover {
      border-color: var(--border-hover);
      box-shadow: var(--shadow-md), var(--shadow-glow-gold);
      transform: translateY(-2px);
    }
    .template-card h4 {
      color: var(--gold);
      font-size: 0.95em;
      margin-bottom: 4px;
    }
    .template-card .desc {
      font-size: 0.78em;
      color: var(--text-secondary);
      margin-bottom: 10px;
    }
    .template-card .tmpl-stat {
      display: flex;
      justify-content: space-between;
      font-size: 0.82em;
      padding: 2px 0;
    }
    .template-card .tmpl-stat .lbl { color: var(--text-secondary); }
    .template-card .tmpl-stat .val { color: var(--text-primary); font-weight: 600; font-variant-numeric: tabular-nums; }
    .template-card .tmpl-units {
      font-size: 0.78em;
      color: var(--text-secondary);
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px solid var(--border);
    }

    .stat-better { color: #2ecc71; }
    .stat-worse { color: var(--accent); }
  `;
  document.head.appendChild(style);
}

// ---------------------------------------------------------------------------
// Navigation bar (duplicated from main.ts to keep this standalone-importable)
// ---------------------------------------------------------------------------

function navBar(active: string): string {
  const link = (href: string, label: string) => {
    const cls = active === href ? ' class="active"' : '';
    return `<a href="#${href}"${cls}>${label}</a>`;
  };
  return `
    <nav>
      <div class="container">
        <a class="brand" href="#/">V3 Save Analyzer</a>
        <div class="nav-links">
          ${link('/', 'Home')}
          ${link('/upload', 'Upload')}
          ${link('/army', 'Army')}
        </div>
      </div>
    </nav>`;
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

interface ArmyState {
  techs: Set<string>;
  traits: Set<string>;
  orderId: string;
  vetLevel: number;
  totalBn: number;
  builderCounts: Record<string, number>;
  traitSections: Record<string, boolean>; // open state
}

function defaultState(): ArmyState {
  return {
    techs: new Set(),
    traits: new Set(),
    orderId: 'advance',
    vetLevel: 0,
    totalBn: 20,
    builderCounts: {},
    traitSections: { skill: true, personality: false, condition: false },
  };
}

// ---------------------------------------------------------------------------
// Core logic helpers
// ---------------------------------------------------------------------------

function getAvailableUnits(techs: Set<string>): Unit[] {
  // A unit is available if its tech is null or its tech is selected
  const available = UNITS.filter(u => u.tech === null || techs.has(u.tech));

  // Hide superseded units: if an upgrade is available, hide the base
  const hidden = new Set<string>();
  for (const u of available) {
    const upgrades = UPGRADES[u.id];
    if (upgrades) {
      // If any upgrade is also available, hide this unit
      if (upgrades.some(upId => available.some(au => au.id === upId))) {
        hidden.add(u.id);
      }
    }
  }

  return available.filter(u => !hidden.has(u.id));
}

function getActiveMods(st: ArmyState): Record<string, number> {
  const traitMods = TRAITS.filter(t => st.traits.has(t.id)).map(t => t.mods);
  const order = ORDERS.find(o => o.id === st.orderId);
  const orderMods = order ? order.mods : {};
  return mergeMods(...traitMods, orderMods);
}

function isOrderAvailable(order: Order, selectedTraits: Set<string>): boolean {
  if (!order.requires) return true;
  const required = order.requires.split('|');
  return required.some(t => selectedTraits.has(t));
}

// ---------------------------------------------------------------------------
// Optimal compositions
// ---------------------------------------------------------------------------

interface TemplateResult {
  name: string;
  desc: string;
  composition: Array<{ unit: Unit; count: number }>;
  totals: EffectiveStats;
}

function bestUnitForGroup(group: string, units: Unit[], mods: Record<string, number>, vetLevel: number): Unit | null {
  const groupUnits = units.filter(u => u.group === group);
  if (groupUnits.length === 0) return null;
  let best = groupUnits[0];
  let bestScore = -Infinity;
  for (const u of groupUnits) {
    const s = computeStats(u, mods, vetLevel);
    const score = s.offense + s.defense;
    if (score > bestScore) {
      bestScore = score;
      best = u;
    }
  }
  return best;
}

function buildTemplate(
  name: string,
  desc: string,
  ratios: Record<string, number>,
  units: Unit[],
  mods: Record<string, number>,
  vetLevel: number,
  totalBn: number,
): TemplateResult | null {
  const composition: Array<{ unit: Unit; count: number }> = [];
  const entries = Object.entries(ratios);

  // Check all groups available
  for (const [group] of entries) {
    // For tanks, check specific unit IDs
    if (group === 'tanks') {
      const tankUnits = units.filter(u => u.id === 'heavy_tank' || u.id === 'light_tanks');
      if (tankUnits.length === 0) return null;
    } else {
      const best = bestUnitForGroup(group, units, mods, vetLevel);
      if (!best) return null;
    }
  }

  let remaining = totalBn;
  for (let i = 0; i < entries.length; i++) {
    const [group, ratio] = entries[i];
    const count = i === entries.length - 1 ? remaining : Math.round(totalBn * ratio);
    remaining -= count;
    if (count <= 0) continue;

    let unit: Unit | null;
    if (group === 'tanks') {
      const tankUnits = units.filter(u => u.id === 'heavy_tank' || u.id === 'light_tanks');
      unit = tankUnits.length > 0 ? tankUnits.reduce((a, b) => {
        const sa = computeStats(a, mods, vetLevel);
        const sb = computeStats(b, mods, vetLevel);
        return (sa.offense + sa.defense) > (sb.offense + sb.defense) ? a : b;
      }) : null;
    } else {
      unit = bestUnitForGroup(group, units, mods, vetLevel);
    }

    if (unit && count > 0) {
      composition.push({ unit, count });
    }
  }

  // Compute totals
  const totals: EffectiveStats = { offense: 0, defense: 0, moraleLoss: 0, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0, speed: 0 };
  let totalCount = 0;
  for (const { unit, count } of composition) {
    const s = computeStats(unit, mods, vetLevel);
    totals.offense += s.offense * count;
    totals.defense += s.defense * count;
    totals.moraleLoss += s.moraleLoss * count;
    totals.killRate += s.killRate * count;
    totals.moraleDamage += s.moraleDamage * count;
    totals.devastation += s.devastation * count;
    totals.occupation += s.occupation * count;
    totals.speed += s.speed * count;
    totalCount += count;
  }
  if (totalCount > 0) {
    totals.moraleLoss /= totalCount;
    totals.killRate /= totalCount;
    totals.moraleDamage /= totalCount;
    totals.devastation /= totalCount;
    totals.occupation /= totalCount;
    totals.speed /= totalCount;
  }

  return { name, desc, composition, totals };
}

function getTemplates(units: Unit[], mods: Record<string, number>, vetLevel: number, totalBn: number): TemplateResult[] {
  const results: TemplateResult[] = [];
  const hasCav = units.some(u => u.group === 'cavalry');
  const hasArt = units.some(u => u.group === 'artillery');
  const hasTanks = units.some(u => u.id === 'heavy_tank' || u.id === 'light_tanks');

  const t1 = buildTemplate('Offensive (Meta)', 'Community consensus best offensive composition', { infantry: 0.5, artillery: 0.5 }, units, mods, vetLevel, totalBn);
  if (t1) results.push(t1);

  const t2 = buildTemplate('Defensive', 'Cheap, holds the line', { infantry: 0.9, artillery: 0.1 }, units, mods, vetLevel, totalBn);
  if (t2) results.push(t2);

  if (hasArt && hasCav) {
    const t3 = buildTemplate('Balanced', 'Infantry, artillery, and cavalry blend', { infantry: 0.5, artillery: 0.4, cavalry: 0.1 }, units, mods, vetLevel, totalBn);
    if (t3) results.push(t3);
  }

  if (hasCav) {
    const t4 = buildTemplate('Colonial / Blitz', 'Fast-moving cavalry-heavy force', { infantry: 0.5, cavalry: 0.5 }, units, mods, vetLevel, totalBn);
    if (t4) results.push(t4);
  }

  if (hasTanks) {
    const t5 = buildTemplate('Armored Offensive', 'Modern combined-arms with tanks', { infantry: 0.4, artillery: 0.4, tanks: 0.2 }, units, mods, vetLevel, totalBn);
    if (t5) results.push(t5);
  }

  return results;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

export function renderArmyPage(app: HTMLElement): void {
  injectStyles();

  const st = defaultState();

  function render(): void {
    const mods = getActiveMods(st);
    const availUnits = getAvailableUnits(st.techs);

    app.innerHTML = `
      ${navBar('/army')}
      <div class="container">
        <h1>Army Composition Optimizer<small>Configure technologies, generals, and orders</small></h1>
        <div class="army-layout">
          <div class="army-sidebar" id="army-sidebar">
            ${renderTechPanel(st)}
            ${renderTraitsPanel(st)}
            ${renderOrdersPanel(st)}
            ${renderVetPanel(st)}
            ${renderBnPanel(st)}
          </div>
          <div class="army-main">
            <h2 style="margin-top:0">Unit Stats</h2>
            ${renderUnitTable(availUnits, mods, st.vetLevel)}
            <h2>Army Builder</h2>
            ${renderBuilder(availUnits, mods, st)}
            <h2>Optimal Compositions</h2>
            ${renderTemplates(availUnits, mods, st.vetLevel, st.totalBn)}
          </div>
        </div>
      </div>
      <footer>Victoria 3 Army Optimizer — Game data may vary with patches.</footer>
    `;

    attachEvents(st, render);
  }

  render();
}

// ---------------------------------------------------------------------------
// Sidebar panels
// ---------------------------------------------------------------------------

function renderTechPanel(st: ArmyState): string {
  const eras = [1, 2, 3, 4, 5];
  let html = `<div class="army-panel"><h3>Technologies</h3>`;
  html += `<div class="era-btns">`;
  for (const e of eras) {
    html += `<button class="era-btn" data-era="${e}">Era ${e}</button>`;
  }
  html += `<button class="era-btn" data-era="clear">Clear All</button>`;
  html += `</div>`;
  for (const e of eras) {
    const techs = TECHNOLOGIES.filter(t => t.era === e);
    if (techs.length === 0) continue;
    html += `<div class="era-group"><div class="era-label">Era ${e}</div>`;
    for (const t of techs) {
      const checked = st.techs.has(t.id) ? ' checked' : '';
      html += `<div class="check-row"><input type="checkbox" id="tech-${t.id}" data-tech="${t.id}"${checked}><label for="tech-${t.id}">${t.name}</label></div>`;
    }
    html += `</div>`;
  }
  html += `</div>`;
  return html;
}

function renderTraitsPanel(st: ArmyState): string {
  let html = `<div class="army-panel"><h3>General Traits</h3>`;
  const categories: Array<{ key: 'skill' | 'personality' | 'condition'; label: string }> = [
    { key: 'skill', label: 'Skill Traits' },
    { key: 'personality', label: 'Personality Traits' },
    { key: 'condition', label: 'Conditions' },
  ];
  for (const cat of categories) {
    const isOpen = st.traitSections[cat.key];
    const traits = TRAITS.filter(t => t.category === cat.key);
    html += `<div class="trait-section">`;
    html += `<div class="trait-section-header" data-trait-cat="${cat.key}">`;
    html += `<span>${cat.label} (${traits.length})</span>`;
    html += `<span class="chevron ${isOpen ? 'open' : ''}">▶</span>`;
    html += `</div>`;
    html += `<div class="trait-section-body${isOpen ? '' : ' collapsed'}">`;
    for (const t of traits) {
      const checked = st.traits.has(t.id) ? ' checked' : '';
      const hint = Object.keys(t.mods).length > 0 ? ` <span class="mod-hint">${modSummary(t.mods)}</span>` : '';
      html += `<div class="check-row"><input type="checkbox" id="trait-${t.id}" data-trait="${t.id}"${checked}><label for="trait-${t.id}">${t.name}${hint}</label></div>`;
    }
    html += `</div></div>`;
  }
  html += `</div>`;
  return html;
}

function renderOrdersPanel(st: ArmyState): string {
  let html = `<div class="army-panel"><h3>Orders</h3>`;
  for (const o of ORDERS) {
    const avail = isOrderAvailable(o, st.traits);
    const checked = st.orderId === o.id ? ' checked' : '';
    const disabled = !avail ? ' disabled' : '';
    const rowCls = !avail ? ' order-disabled' : '';
    const hint = ` <span class="mod-hint">${modSummary(o.mods)}</span>`;
    html += `<div class="check-row${rowCls}"><input type="radio" name="order" id="order-${o.id}" data-order="${o.id}" value="${o.id}"${checked}${disabled}><label for="order-${o.id}">${o.name}${hint}</label></div>`;
  }
  html += `</div>`;
  return html;
}

function renderVetPanel(st: ArmyState): string {
  let html = `<div class="army-panel"><h3>Veterancy</h3><select class="vet-select" id="vet-select">`;
  for (const v of VETERANCY) {
    const sel = v.level === st.vetLevel ? ' selected' : '';
    html += `<option value="${v.level}"${sel}>${v.name}</option>`;
  }
  html += `</select></div>`;
  return html;
}

function renderBnPanel(st: ArmyState): string {
  return `<div class="army-panel">
    <h3>Total Battalions</h3>
    <div style="display:flex;gap:8px;align-items:center">
      <input type="number" class="bn-input" id="bn-input" min="1" max="100" value="${st.totalBn}">
    </div>
  </div>`;
}

// ---------------------------------------------------------------------------
// Unit stats table
// ---------------------------------------------------------------------------

function renderUnitTable(units: Unit[], mods: Record<string, number>, vetLevel: number): string {
  const groups: Array<{ key: string; label: string }> = [
    { key: 'infantry', label: 'Infantry' },
    { key: 'artillery', label: 'Artillery' },
    { key: 'cavalry', label: 'Cavalry' },
  ];

  let html = `<div style="overflow-x:auto"><table>
    <thead><tr>
      <th>Unit</th><th class="num">Offense</th><th class="num">Defense</th>
      <th class="num">Morale Loss</th><th class="num">Kill Rate</th>
      <th class="num">Morale Dmg</th><th class="num">Devastation</th>
      <th class="num">Occupation</th><th class="num">Speed</th><th>Upkeep</th>
    </tr></thead><tbody>`;

  for (const g of groups) {
    const groupUnits = units.filter(u => u.group === g.key);
    if (groupUnits.length === 0) continue;
    html += `<tr class="unit-group-header"><td colspan="10" style="color:${GROUP_COLORS[g.key]}">${g.label}</td></tr>`;
    for (const u of groupUnits) {
      const s = computeStats(u, mods, vetLevel);
      const upkeepStr = u.upkeep.length > 0
        ? u.upkeep.map(up => `${up.qty} ${goodName(up.good)}`).join(', ')
        : '—';
      html += `<tr>
        <td><div class="unit-name-cell"><span class="unit-dot" style="background:${GROUP_COLORS[u.group]}"></span><div>${u.name}<span class="unit-base">Base: ${u.offense}/${u.defense}</span></div></div></td>
        <td class="num">${fmtNum(s.offense)}</td>
        <td class="num">${fmtNum(s.defense)}</td>
        <td class="num">${fmtNum(s.moraleLoss)}</td>
        <td class="num">${fmtPct(s.killRate)}</td>
        <td class="num">${fmtNum(s.moraleDamage, 2)}</td>
        <td class="num">${fmtNum(s.devastation, 2)}</td>
        <td class="num">${fmtPct(s.occupation)}</td>
        <td class="num">${s.speed > 0 ? '+' : ''}${fmtNum(s.speed, 2)}</td>
        <td style="font-size:0.78em;color:var(--text-secondary)">${upkeepStr}</td>
      </tr>`;
    }
  }
  html += `</tbody></table></div>`;
  return html;
}

// ---------------------------------------------------------------------------
// Army builder
// ---------------------------------------------------------------------------

function renderBuilder(units: Unit[], mods: Record<string, number>, st: ArmyState): string {
  // Ensure counts exist for all available units
  for (const u of units) {
    if (!(u.id in st.builderCounts)) st.builderCounts[u.id] = 0;
  }
  // Remove counts for unavailable units
  for (const id of Object.keys(st.builderCounts)) {
    if (!units.find(u => u.id === id)) delete st.builderCounts[id];
  }

  const totalUsed = Object.values(st.builderCounts).reduce((a, b) => a + b, 0);
  const totals: EffectiveStats = { offense: 0, defense: 0, moraleLoss: 0, killRate: 0, moraleDamage: 0, devastation: 0, occupation: 0, speed: 0 };
  let infCount = 0;

  for (const u of units) {
    const count = st.builderCounts[u.id] ?? 0;
    if (count <= 0) continue;
    const s = computeStats(u, mods, st.vetLevel);
    totals.offense += s.offense * count;
    totals.defense += s.defense * count;
    totals.moraleLoss += s.moraleLoss * count;
    totals.killRate += s.killRate * count;
    totals.moraleDamage += s.moraleDamage * count;
    totals.devastation += s.devastation * count;
    totals.occupation += s.occupation * count;
    totals.speed += s.speed * count;
    if (u.group === 'infantry') infCount += count;
  }
  if (totalUsed > 0) {
    totals.moraleLoss /= totalUsed;
    totals.killRate /= totalUsed;
    totals.moraleDamage /= totalUsed;
    totals.devastation /= totalUsed;
    totals.occupation /= totalUsed;
    totals.speed /= totalUsed;
  }

  const infPct = totalUsed > 0 ? infCount / totalUsed : 0;
  const warning = totalUsed > 0 && infPct < 0.5
    ? `<div class="warning-banner">⚠️ Infantry is below 50% (${(infPct * 100).toFixed(0)}%). Armies require at least half infantry for front-line coverage.</div>`
    : '';

  let html = warning;
  html += `<div style="overflow-x:auto"><table>
    <thead><tr>
      <th>Unit</th><th class="num" style="width:70px">Count</th>
      <th class="num">Offense</th><th class="num">Defense</th>
      <th class="num">Morale Loss</th><th class="num">Kill Rate</th>
    </tr></thead><tbody>`;

  for (const u of units) {
    const count = st.builderCounts[u.id] ?? 0;
    const s = computeStats(u, mods, st.vetLevel);
    html += `<tr class="builder-row">
      <td><div class="unit-name-cell"><span class="unit-dot" style="background:${GROUP_COLORS[u.group]}"></span>${u.name}</div></td>
      <td class="num"><input type="number" class="bn-count-input" data-builder="${u.id}" min="0" max="100" value="${count}"></td>
      <td class="num">${count > 0 ? fmtNum(s.offense * count) : '—'}</td>
      <td class="num">${count > 0 ? fmtNum(s.defense * count) : '—'}</td>
      <td class="num">${count > 0 ? fmtNum(s.moraleLoss) : '—'}</td>
      <td class="num">${count > 0 ? fmtPct(s.killRate) : '—'}</td>
    </tr>`;
  }

  html += `<tr class="builder-totals">
    <td>Total (${totalUsed} bn)</td>
    <td></td>
    <td class="num">${fmtNum(totals.offense)}</td>
    <td class="num">${fmtNum(totals.defense)}</td>
    <td class="num">${totalUsed > 0 ? fmtNum(totals.moraleLoss) : '—'}</td>
    <td class="num">${totalUsed > 0 ? fmtPct(totals.killRate) : '—'}</td>
  </tr>`;
  html += `</tbody></table></div>`;
  return html;
}

// ---------------------------------------------------------------------------
// Optimal composition templates
// ---------------------------------------------------------------------------

function renderTemplates(units: Unit[], mods: Record<string, number>, vetLevel: number, totalBn: number): string {
  const templates = getTemplates(units, mods, vetLevel, totalBn);
  if (templates.length === 0) {
    return `<p style="color:var(--text-secondary)">Select some technologies to unlock units and see recommended compositions.</p>`;
  }

  let html = `<div class="template-grid">`;
  for (const t of templates) {
    const unitList = t.composition.map(c => `${c.count}× ${c.unit.name}`).join(', ');
    html += `<div class="template-card">
      <h4>${t.name}</h4>
      <div class="desc">${t.desc}</div>
      <div class="tmpl-stat"><span class="lbl">Total Offense</span><span class="val">${fmtNum(t.totals.offense)}</span></div>
      <div class="tmpl-stat"><span class="lbl">Total Defense</span><span class="val">${fmtNum(t.totals.defense)}</span></div>
      <div class="tmpl-stat"><span class="lbl">Avg Morale Loss</span><span class="val">${fmtNum(t.totals.moraleLoss)}</span></div>
      <div class="tmpl-stat"><span class="lbl">Avg Kill Rate</span><span class="val">${fmtPct(t.totals.killRate)}</span></div>
      <div class="tmpl-stat"><span class="lbl">Avg Devastation</span><span class="val">${fmtNum(t.totals.devastation, 2)}</span></div>
      <div class="tmpl-units">${unitList}</div>
    </div>`;
  }
  html += `</div>`;
  return html;
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------

function attachEvents(st: ArmyState, render: () => void): void {
  // Tech checkboxes
  document.querySelectorAll<HTMLInputElement>('[data-tech]').forEach(el => {
    el.addEventListener('change', () => {
      const techId = el.dataset.tech!;
      if (el.checked) st.techs.add(techId);
      else st.techs.delete(techId);
      render();
    });
  });

  // Era quick-select buttons
  document.querySelectorAll<HTMLButtonElement>('[data-era]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const era = btn.dataset.era!;
      if (era === 'clear') {
        st.techs.clear();
      } else {
        const eraNum = parseInt(era);
        const eraTechs = TECHNOLOGIES.filter(t => t.era <= eraNum);
        for (const t of eraTechs) st.techs.add(t.id);
      }
      render();
    });
  });

  // Trait section collapsers
  document.querySelectorAll<HTMLElement>('[data-trait-cat]').forEach(el => {
    el.addEventListener('click', () => {
      const cat = el.dataset.traitCat!;
      st.traitSections[cat] = !st.traitSections[cat];
      render();
    });
  });

  // Trait checkboxes
  document.querySelectorAll<HTMLInputElement>('[data-trait]').forEach(el => {
    el.addEventListener('change', () => {
      const traitId = el.dataset.trait!;
      if (el.checked) st.traits.add(traitId);
      else st.traits.delete(traitId);
      // If current order requires a trait that was just deselected, reset to 'advance'
      const currentOrder = ORDERS.find(o => o.id === st.orderId);
      if (currentOrder && !isOrderAvailable(currentOrder, st.traits)) {
        st.orderId = 'advance';
      }
      render();
    });
  });

  // Order radios
  document.querySelectorAll<HTMLInputElement>('[data-order]').forEach(el => {
    el.addEventListener('change', () => {
      st.orderId = el.value;
      render();
    });
  });

  // Veterancy select
  const vetSel = document.getElementById('vet-select') as HTMLSelectElement | null;
  if (vetSel) {
    vetSel.addEventListener('change', () => {
      st.vetLevel = parseInt(vetSel.value);
      render();
    });
  }

  // Total battalions
  const bnInput = document.getElementById('bn-input') as HTMLInputElement | null;
  if (bnInput) {
    bnInput.addEventListener('change', () => {
      const val = parseInt(bnInput.value);
      if (!isNaN(val) && val >= 1 && val <= 100) st.totalBn = val;
      render();
    });
  }

  // Builder count inputs
  document.querySelectorAll<HTMLInputElement>('[data-builder]').forEach(el => {
    el.addEventListener('change', () => {
      const uid = el.dataset.builder!;
      const val = parseInt(el.value);
      st.builderCounts[uid] = isNaN(val) || val < 0 ? 0 : val;
      render();
    });
  });
}
