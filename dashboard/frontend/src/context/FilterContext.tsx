/**
 * FilterContext for managing dashboard filter state.
 * 
 * Provides centralized state management for date range, unit, shift, and quality filters.
 */
import { createContext, useContext, useState, ReactNode } from 'react';
import { FilterState } from '../types/analytics';

interface FilterContextType {
  filters: FilterState;
  setDateRange: (from: Date, to: Date) => void;
  setUnitId: (unitId?: string) => void;
  setShift: (shift?: 'morning' | 'afternoon' | 'night') => void;
  setExcludeLowQuality: (exclude: boolean) => void;
  resetFilters: () => void;
}

const FilterContext = createContext<FilterContextType | undefined>(undefined);

/**
 * Get default date range (last 30 days).
 */
function getDefaultDateRange(): { from: Date; to: Date } {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 30);
  return { from, to };
}

/**
 * FilterContext provider component.
 */
export function FilterProvider({ children }: { children: ReactNode }) {
  const defaultRange = getDefaultDateRange();
  
  const [filters, setFilters] = useState<FilterState>({
    dateFrom: defaultRange.from,
    dateTo: defaultRange.to,
    unitId: undefined,
    shift: undefined,
    excludeLowQuality: false,
  });

  const setDateRange = (from: Date, to: Date) => {
    setFilters((prev) => ({ ...prev, dateFrom: from, dateTo: to }));
  };

  const setUnitId = (unitId?: string) => {
    setFilters((prev) => ({ ...prev, unitId }));
  };

  const setShift = (shift?: 'morning' | 'afternoon' | 'night') => {
    setFilters((prev) => ({ ...prev, shift }));
  };

  const setExcludeLowQuality = (exclude: boolean) => {
    setFilters((prev) => ({ ...prev, excludeLowQuality: exclude }));
  };

  const resetFilters = () => {
    const defaultRange = getDefaultDateRange();
    setFilters({
      dateFrom: defaultRange.from,
      dateTo: defaultRange.to,
      unitId: undefined,
      shift: undefined,
      excludeLowQuality: false,
    });
  };

  return (
    <FilterContext.Provider
      value={{
        filters,
        setDateRange,
        setUnitId,
        setShift,
        setExcludeLowQuality,
        resetFilters,
      }}
    >
      {children}
    </FilterContext.Provider>
  );
}

/**
 * Hook to access FilterContext.
 */
export function useFilters(): FilterContextType {
  const context = useContext(FilterContext);
  if (!context) {
    throw new Error('useFilters must be used within a FilterProvider');
  }
  return context;
}
