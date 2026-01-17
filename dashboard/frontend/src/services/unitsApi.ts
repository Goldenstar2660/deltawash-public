/**
 * Units API client functions.
 */
import api from './api';

export interface Unit {
  id: string;
  unit_name: string;
  unit_code: string;
}

/**
 * Fetch all units.
 */
export async function fetchUnits(): Promise<Unit[]> {
  const response = await api.get<Unit[]>('/units');
  return response.data;
}
