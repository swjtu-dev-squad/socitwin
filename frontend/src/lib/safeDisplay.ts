/**
 * Safe Display Utilities
 *
 * Provides utility functions for safely displaying data that may be null, undefined, or invalid.
 * Missing values display as "--" while valid zeros display as "0".
 */

/**
 * Safely display a numeric metric value
 * @param value - The number to display (can be null, undefined, or NaN)
 * @returns "--" for missing/invalid values, otherwise the number as string
 *
 * @example
 * displayMetric(0)        // "0"
 * displayMetric(42)       // "42"
 * displayMetric(null)     // "--"
 * displayMetric(undefined) // "--"
 * displayMetric(NaN)      // "--"
 */
export function displayMetric(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return String(value)
}

/**
 * Safely display a text value
 * @param value - The string to display (can be null or undefined)
 * @returns "--" for missing values, otherwise the string
 *
 * @example
 * displayText("hello")   // "hello"
 * displayText("")        // ""
 * displayText(null)      // "--"
 * displayText(undefined) // "--"
 */
export function displayText(value: string | null | undefined): string {
  if (value === null || value === undefined) {
    return '--'
  }
  return value
}

/**
 * Safely display a percentage value
 * @param value - The number to display as percentage (can be null, undefined, or NaN)
 * @returns "--" for missing/invalid values, otherwise the number with "%" suffix
 *
 * @example
 * displayPercentage(0)        // "0%"
 * displayPercentage(50.5)     // "50.5%"
 * displayPercentage(null)     // "--"
 * displayPercentage(undefined) // "--"
 * displayPercentage(NaN)      // "--"
 */
export function displayPercentage(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return `${value}%`
}

/**
 * Safely display a count value
 * @param value - The number to display (can be null, undefined, or NaN)
 * @returns "--" for missing/invalid values, otherwise the number as string
 *
 * @example
 * displayCount(0)        // "0"
 * displayCount(100)      // "100"
 * displayCount(null)     // "--"
 * displayCount(undefined) // "--"
 * displayCount(NaN)      // "--"
 */
export function displayCount(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return String(value)
}

/**
 * Safely display a formatted numeric value with decimal places
 * @param value - The number to format (can be null, undefined, or NaN)
 * @param decimals - Number of decimal places (default: 1)
 * @returns "--" for missing/invalid values, otherwise formatted string
 *
 * @example
 * displayMetricFormatted(3.14159, 2)  // "3.14"
 * displayMetricFormatted(0, 1)        // "0.0"
 * displayMetricFormatted(null, 1)     // "--"
 * displayMetricFormatted(undefined, 1) // "--"
 */
export function displayMetricFormatted(
  value: number | null | undefined,
  decimals: number = 1
): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return value.toFixed(decimals)
}

/**
 * Safely display a percentage with formatting
 * @param value - The number to display as percentage (can be null, undefined, or NaN)
 * @param decimals - Number of decimal places (default: 1)
 * @returns "--" for missing/invalid values, otherwise formatted percentage string
 *
 * @example
 * displayPercentageFormatted(66.666, 1)  // "66.7%"
 * displayPercentageFormatted(0, 1)        // "0.0%"
 * displayPercentageFormatted(null, 1)     // "--"
 */
export function displayPercentageFormatted(
  value: number | null | undefined,
  decimals: number = 1
): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return '--'
  }
  return `${value.toFixed(decimals)}%`
}

/**
 * Safely display a ratio/value with unit
 * @param numerator - The numerator (can be null, undefined, or NaN)
 * @param denominator - The denominator (can be null, undefined, or NaN)
 * @param separator - Separator between values (default: " / ")
 * @returns "--" for missing/invalid values, otherwise formatted ratio string
 *
 * @example
 * displayRatio(10, 20)      // "10 / 20"
 * displayRatio(0, 0)        // "0 / 0"
 * displayRatio(null, 20)    // "-- / 20"
 * displayRatio(10, undefined) // "10 / --"
 */
export function displayRatio(
  numerator: number | null | undefined,
  denominator: number | null | undefined,
  separator: string = ' / '
): string {
  const safeNum = displayCount(numerator)
  const safeDen = displayCount(denominator)
  return `${safeNum}${separator}${safeDen}`
}

/**
 * Safely display a location (country/city combination)
 * @param country - Country name (can be null, undefined, or empty)
 * @param city - City name (can be null, undefined, or empty)
 * @param separator - Separator between country and city (default: " / ")
 * @returns "--" for missing values, otherwise formatted location string
 *
 * @example
 * displayLocation("USA", "NYC")        // "USA / NYC"
 * displayLocation("USA", undefined)   // "USA"
 * displayLocation(null, "NYC")        // "NYC"
 * displayLocation(null, null)         // "--"
 */
export function displayLocation(
  country: string | null | undefined,
  city: string | null | undefined,
  separator: string = ' / '
): string {
  const parts = [country, city].filter(v => v !== null && v !== undefined && v !== '')
  return parts.length > 0 ? parts.join(separator) : '--'
}

/**
 * Check if a value is "empty" (null, undefined, NaN, or empty string/array)
 * @param value - The value to check
 * @returns true if the value is considered empty
 */
export function isEmpty(value: any): value is null | undefined | '' | [] {
  if (value === null || value === undefined) {
    return true
  }
  if (typeof value === 'string' && value.trim() === '') {
    return true
  }
  if (Array.isArray(value) && value.length === 0) {
    return true
  }
  if (typeof value === 'number' && Number.isNaN(value)) {
    return true
  }
  return false
}
