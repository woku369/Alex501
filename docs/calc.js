// Reine Berechnungsfunktionen der Alex 501 Mazerat-Interpolation (Portierung von calculations.py).
// Keine Abhängigkeit von Browser oder Oberfläche; wird in tests-js/ gegen die Python-Ergebnisse geprüft.

import { DICHTE_START, DICHTE_SCHRITT, VOL_PROZENT } from './alkoholtabelle.js';

/** Entspricht ValueError in Python: fachlich unmögliche oder ungültige Eingaben. */
export class CalcError extends Error {}

/** Formatiert Zahlen mit deutschem Komma. */
export function formatDe(value, decimals = 2) {
  return value.toFixed(decimals).replace('.', ',');
}

/** Korrigiert das Volumen auf 20 °C (Ethanol: 0,11 %/K, Wasser: 0,025 %/K, lineare Näherung). */
export function correctVolumeTemp(volume, temp, isWater = false) {
  const coeff = isWater ? 0.00025 : 0.0011;
  return volume / (1 + coeff * (temp - 20.0));
}

/** Dichte von luftfreiem Wasser in g/cm³ nach Tanaka et al. (2001), gültig für 0-40 °C. */
export function waterDensityTemp(temp) {
  const [a1, a2, a3, a4, a5] = [-3.983035, 301.797, 522528.9, 69.34881, 999.974950]; // a5 in kg/m³
  return (a5 * (1 - ((temp + a1) ** 2 * (temp + a2)) / (a3 * (temp + a4)))) / 1000;
}

// Alkoholtabelle: Dichte in Luft -> wahre Dichte (Vakuum), konventionelle Werte (Luft 0,0012 g/cm³, Gewichte 8,0 g/cm³)
const AIR_DENSITY = 0.0012;
const WEIGHT_DENSITY = 8.0;
const EXTRAPOLATION_POINTS = 50;

// Aufsteigend nach Alkoholgehalt sortiert (die Tabelle läuft nach Dichte aufsteigend)
const ALCOHOL_TABLE = VOL_PROZENT.slice().reverse();
const DENSITY_AIR_TABLE = VOL_PROZENT.map((_, i) => DICHTE_START + DICHTE_SCHRITT * i).reverse();

/** Lineare Regression y = slope * x + intercept (wie numpy.polyfit mit Grad 1). */
export function linearFit(x, y) {
  const n = x.length;
  const meanX = x.reduce((a, b) => a + b, 0) / n;
  const meanY = y.reduce((a, b) => a + b, 0) / n;
  let sxx = 0;
  let sxy = 0;
  for (let i = 0; i < n; i++) {
    sxx += (x[i] - meanX) ** 2;
    sxy += (x[i] - meanX) * (y[i] - meanY);
  }
  const slope = sxy / sxx;
  return { slope, intercept: meanY - slope * meanX };
}

/** Lineare Interpolation wie numpy.interp (xp aufsteigend; außerhalb wird der Randwert geliefert). */
function interp(x, xp, fp) {
  if (x <= xp[0]) return fp[0];
  if (x >= xp[xp.length - 1]) return fp[fp.length - 1];
  let low = 0;
  let high = xp.length - 1;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if (xp[middle] <= x) low = middle;
    else high = middle;
  }
  const slope = (fp[high] - fp[low]) / (xp[high] - xp[low]);
  return fp[low] + slope * (x - xp[low]);
}

/** Wahre Dichte aus der scheinbaren Dichte in Luft: rho = (rho_Luft + rho_a) / (1 + rho_a / rho_Gewicht). */
export function densityInAirToTrue(densityAir) {
  return (densityAir + AIR_DENSITY) / (1 + AIR_DENSITY / WEIGHT_DENSITY);
}

const LOW_FIT = linearFit(ALCOHOL_TABLE.slice(0, EXTRAPOLATION_POINTS), DENSITY_AIR_TABLE.slice(0, EXTRAPOLATION_POINTS));
const HIGH_FIT = linearFit(ALCOHOL_TABLE.slice(-EXTRAPOLATION_POINTS), DENSITY_AIR_TABLE.slice(-EXTRAPOLATION_POINTS));

/** Wahre Dichte (g/cm³) einer Ethanol-Wasser-Mischung bei 20 °C aus dem Alkoholgehalt (%vol). */
export function interpolateDensityFromAlcohol(alc) {
  alc = Math.min(Math.max(Number(alc), 0.0), 100.0);
  let densityAir;
  if (alc < ALCOHOL_TABLE[0]) densityAir = LOW_FIT.slope * alc + LOW_FIT.intercept;
  else if (alc > ALCOHOL_TABLE[ALCOHOL_TABLE.length - 1]) densityAir = HIGH_FIT.slope * alc + HIGH_FIT.intercept;
  else densityAir = interp(alc, ALCOHOL_TABLE, DENSITY_AIR_TABLE);
  return densityInAirToTrue(densityAir);
}

const ETHANOL_DENSITY_20 = interpolateDensityFromAlcohol(100); // g/cm³, reines Ethanol bei 20 °C
const WATER_DENSITY_20 = waterDensityTemp(20.0); // g/cm³
export { ETHANOL_DENSITY_20, WATER_DENSITY_20 };

/** Massenanteil Ethanol (0-1) aus %vol: w = phi * rho_Ethanol / rho_Mischung. */
export function alcoholMassFraction(volPercent) {
  return ((volPercent / 100) * ETHANOL_DENSITY_20) / interpolateDensityFromAlcohol(volPercent);
}

/** Korrigiert die Dichte von der aktuellen Temperatur auf 20 °C (lineare Näherung zwischen Wasser und Ethanol). */
export function correctDensityTo20C(densityAtTemp, temp, alcPercent) {
  const coeffWater = -0.0002;
  const coeffEthanol = -0.0009;
  const coeff = coeffWater + (coeffEthanol - coeffWater) * (alcPercent / 100);
  return densityAtTemp - coeff * (temp - 20.0);
}

/** Lineare Kalibrierkurve (Paare [Referenzwert, Messwert]): Messwert -> korrigierter Wert. */
export function applyCalibrationCurve(calibData, value) {
  const refs = calibData.map((p) => p[0]);
  const meas = calibData.map((p) => p[1]);
  const { slope, intercept } = linearFit(meas, refs);
  return slope * value + intercept;
}

/** Verdünnungsfaktor aus Probe- und Wasservolumen (ohne Kontraktion). */
export function computeDilutionFactor(probeVol, waterVol) {
  return (probeVol + waterVol) / probeVol;
}

/**
 * Rechnet den gemessenen Alkoholgehalt (%vol, 20 °C) der verdünnten Probe auf die Originalprobe zurück
 * (vor einer Kalibrierung), per Massenbilanz mit Volumenkontraktion (Bisektion, siehe calculations.py).
 */
export function computeActualAlcohol(measuredAlc, probeVol, waterVol) {
  if (measuredAlc <= 0) return 0.0;
  const ethanolFractionDiluted = alcoholMassFraction(measuredAlc);
  const balance = (phi) => {
    const ethanolMass = (probeVol * phi / 100) * ETHANOL_DENSITY_20;
    const totalMass = interpolateDensityFromAlcohol(phi) * probeVol + WATER_DENSITY_20 * waterVol;
    return ethanolMass - ethanolFractionDiluted * totalMass;
  };
  let low = Number(measuredAlc);
  let high = 100.0;
  // kleine Toleranz gegen numerisches Rauschen bei genau 100 %vol in der Originalprobe
  if (balance(high) < -1e-6 * probeVol * ETHANOL_DENSITY_20) {
    throw new CalcError('Der gemessene Alkoholgehalt ist für diese Verdünnung zu hoch: '
      + 'die Originalprobe müsste mehr als 100 %vol enthalten.');
  }
  for (let i = 0; i < 60; i++) {
    const middle = (low + high) / 2;
    if (balance(middle) < 0) low = middle;
    else high = middle;
  }
  return (low + high) / 2;
}

/** Wirksamer Verdünnungsfaktor V_Verdünnung(real) / V_Probe unter Berücksichtigung der Volumenkontraktion. */
export function computeEffectiveDilutionFactor(measuredAlc, probeVol, waterVol) {
  const actualAlc = computeActualAlcohol(measuredAlc, probeVol, waterVol);
  const totalMass = interpolateDensityFromAlcohol(actualAlc) * probeVol + WATER_DENSITY_20 * waterVol;
  const dilutedVolume = totalMass / interpolateDensityFromAlcohol(measuredAlc);
  return dilutedVolume / probeVol;
}

/** Ansatzplanung: Wassermenge für vorgegebene Probemenge und Zielalkohol (Richtwert, ohne Temperatur). */
export function planDilution(probeAlc, probeVolume, targetAlc = 40.0) {
  if (!(targetAlc > 0 && targetAlc < 100)) throw new CalcError('Der Ziel-Alkoholgehalt muss zwischen 0 und 100 %vol liegen.');
  if (probeAlc <= targetAlc) throw new CalcError('Die Probe liegt nicht über dem Ziel-Alkoholgehalt, eine Verdünnung ist nicht nötig.');
  if (probeVolume <= 0) throw new CalcError('Das Probevolumen muss größer als 0 ml sein.');
  const ethanolFractionTarget = alcoholMassFraction(targetAlc);
  const probeDensity = interpolateDensityFromAlcohol(probeAlc);
  const waterPerProbe = ((probeAlc / 100) * ETHANOL_DENSITY_20 / ethanolFractionTarget - probeDensity) / WATER_DENSITY_20;
  const dilutedPerProbe = (probeDensity + WATER_DENSITY_20 * waterPerProbe) / interpolateDensityFromAlcohol(targetAlc);
  const waterVolume = probeVolume * waterPerProbe;
  return {
    water_volume: waterVolume,
    water_mass: waterVolume * WATER_DENSITY_20,
    total_volume: probeVolume * dilutedPerProbe,
    summed_volume: probeVolume + waterVolume,
  };
}

/** Tatsächliche Dichte der Originalprobe; gibt [actual_density, expected_density_original] zurück. */
export function computeActualDensity(measuredAlc, measuredDens, actualAlcoholPercent, dilutionFactor) {
  const expectedDiluted = interpolateDensityFromAlcohol(measuredAlc);
  const expectedOriginal = interpolateDensityFromAlcohol(actualAlcoholPercent);
  const difference = measuredDens - expectedDiluted;
  return [expectedOriginal + difference * dilutionFactor, expectedOriginal];
}

/** Tatsächlicher Extraktgehalt der Originalprobe. */
export function computeActualExtract(measuredExt, dilutionFactor) {
  return measuredExt * dilutionFactor;
}
