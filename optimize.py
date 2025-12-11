"""Tri-band antenna optimization using genetic algorithm and NEC2 feedback."""
from typing import List, Tuple, Dict, Optional, Callable
import numpy as np
from scipy.optimize import minimize_scalar
from loguru import logger

from core import NEC2Interface, NEC2Error, AntennaMetrics
from design import AntennaDesign, AntennaGeometryError

class OptimizationError(Exception):
    """Custom exception for optimization failures."""
    pass

class TriBandOptimizer:
    """Optimize antenna design for three frequency bands using NEC2 analysis."""

    def __init__(self, nec_interface: NEC2Interface):
        """Initialize optimizer with NEC2 interface."""
        self.nec = nec_interface
        self.designer = AntennaDesign()
        self.generation = 0
        self.max_generations = 20
        self.population_size = 10
        self.elite_count = 2
        logger.info("Tri-band optimizer initialized")

    def optimize_tri_band(self, freq1: float, freq2: float, freq3: float,
                         iterations: int = 50) -> Dict:
        """Optimize antenna for three frequency bands.

        Args:
            freq1, freq2, freq3: Target frequencies in MHz
            iterations: Maximum optimization iterations

        Returns:
            dict: Best optimization results with geometry and performance
        """
        try:
            frequencies = [freq1, freq2, freq3]
            logger.info(f"Starting tri-band optimization for {freq1}/{freq2}/{freq3} MHz")

            # Initialize population with different antenna types
            population = self._initialize_population(frequencies)

            best_fitness = float('inf')
            best_geometry = None
            best_results = None

            for iteration in range(iterations):
                logger.info(f"Optimization iteration {iteration + 1}/{iterations}")

                # Evaluate fitness for each individual
                fitness_scores = []
                for individual in population:
                    try:
                        fitness = self._evaluate_fitness(individual, frequencies)
                        fitness_scores.append((individual, fitness))
                    except (NEC2Error, AntennaGeometryError) as e:
                        logger.warning(f"Individual evaluation failed: {str(e)}")
                        fitness_scores.append((individual, float('inf')))

                # Sort by fitness (lower is better)
                fitness_scores.sort(key=lambda x: x[1])

                # Track best solution
                current_best_fitness = fitness_scores[0][1]
                if current_best_fitness < best_fitness:
                    best_fitness = current_best_fitness
                    best_geometry = fitness_scores[0][0]
                    logger.info(f"New best fitness: {best_fitness:.3f}")

                    # Get detailed results for best geometry
                    try:
                        best_results = self._get_detailed_results(best_geometry, frequencies)
                    except Exception as e:
                        logger.warning(f"Failed to get detailed results: {str(e)}")

                # Check convergence
                if best_fitness < 1.0:  # Good enough fitness
                    logger.info(f"Converged at iteration {iteration + 1}")
                    break

                # Generate next population
                population = self._evolve_population(fitness_scores)

            if best_geometry is None or best_results is None:
                raise OptimizationError("Optimization failed to find valid solution")

            result = {
                'geometry': best_geometry,
                'performance': best_results,
                'fitness': best_fitness,
                'frequencies': frequencies,
                'iterations_completed': iteration + 1
            }

            logger.info(f"Optimization completed with fitness {best_fitness:.3f}")
            return result

        except Exception as e:
            logger.error(f"Tri-band optimization error: {str(e)}")
            raise OptimizationError(f"Optimization failed: {str(e)}")

    def _initialize_population(self, frequencies: List[float]) -> List[Dict]:
        """Generate initial population of antenna designs."""
        population = []

        # Try different antenna combinations
        combinations = [
            ('monopole', 'dipole', 'patch'),
            ('dipole', 'dipole', 'coil'),
            ('monopole', 'coil', 'coil'),
            ('patch', 'patch', 'coil')
        ]

        for combo in combinations:
            for i in range(self.population_size // len(combinations)):
                individual = {
                    'type': combo,
                    'scaling_factors': np.random.uniform(0.8, 1.2, 3),  # Scale elements
                    'position_offsets': np.random.uniform(-0.5, 0.5, 6),  # X,Y offsets for each element
                    'coil_parameters': {
                        'turns': np.random.randint(2, 5),
                        'spacing': np.random.uniform(0.008, 0.015)
                    } if 'coil' in combo else None
                }
                population.append(individual)

        logger.info(f"Initialized population of {len(population)} individuals")
        return population

    def _evaluate_fitness(self, individual: Dict, frequencies: List[float]) -> float:
        """Calculate fitness score for antenna design."""
        try:
            # Generate geometry
            geometry = self._generate_individual_geometry(individual, frequencies)

            if not geometry:
                return float('inf')

            # Run NEC2 simulation
            sim_results = self.nec.run_simulation(geometry, frequencies)

            # Calculate fitness components
            fitness_components = {
                'vswr_penalty': 0.0,
                'gain_penalty': 0.0,
                'impedance_penalty': 0.0,
                'size_penalty': 0.0
            }

            total_vswr_penalty = 0
            total_gain_penalty = 0
            total_impedance_penalty = 0

            for freq, results in sim_results.items():
                validation = AntennaMetrics.validate_performance(results)

                # VSWR penalty (want < 3:1, penalty increases with VSWR)
                vswr = results.get('vswr', float('inf'))
                if vswr > 3.0:
                    total_vswr_penalty += (vswr / 3.0 - 1) ** 2

                # Gain penalty (want > -10 dBi)
                gain = results.get('gain_dbi', -50)
                if gain < -10:
                    total_gain_penalty += (gain + 10) ** 2

                # Impedance penalty (want 30-70 ohms)
                impedance = results.get('impedance_ohms', complex(0, 0))
                if isinstance(impedance, complex):
                    real_part = impedance.real
                    if not (30 <= real_part <= 70):
                        distance = min(abs(real_part - 30), abs(real_part - 70))
                        total_impedance_penalty += distance ** 2

            fitness_components['vswr_penalty'] = total_vswr_penalty / len(frequencies)
            fitness_components['gain_penalty'] = total_gain_penalty / len(frequencies)
            fitness_components['impedance_penalty'] = total_impedance_penalty / len(frequencies)

            # Size penalty (discourage oversized designs)
            size_penalty = self._calculate_size_penalty(geometry)
            fitness_components['size_penalty'] = size_penalty

            # Total fitness (weighted sum of penalties)
            weights = {
                'vswr_penalty': 2.0,      # Most important
                'gain_penalty': 1.5,
                'impedance_penalty': 1.0,
                'size_penalty': 0.5       # Less critical
            }

            total_fitness = sum(weight * component
                              for component, weight in weights.items()
                              for component_name, component in fitness_components.items()
                              if component_name == component)

            return total_fitness

        except (NEC2Error, AntennaGeometryError, Exception) as e:
            logger.warning(f"Fitness evaluation failed: {str(e)}")
            return float('inf')

    def _generate_individual_geometry(self, individual: Dict, frequencies: List[float]) -> Optional[str]:
        """Generate NEC2 geometry for optimization individual."""
        try:
            geometries = []
            tag_offset = 0

            for i, antenna_type in enumerate(individual['type']):
                freq = frequencies[i]
                scaling = individual['scaling_factors'][i]
                x_offset = individual['position_offsets'][i*2]
                y_offset = individual['position_offsets'][i*2 + 1]

                try:
                    if antenna_type == 'monopole':
                        geom = self.designer.generate_monopole(freq * scaling)
                    elif antenna_type == 'dipole':
                        geom = self.designer.generate_dipole(freq * scaling)
                    elif antenna_type == 'patch':
                        geom = self.designer.generate_patch_antenna(freq * scaling)
                    elif antenna_type == 'coil':
                        coil_params = individual.get('coil_parameters', {})
                        turns = coil_params.get('turns', 3)
                        spacing = coil_params.get('spacing', 0.01)
                        geom = self.designer.generate_spiral_coil(freq * scaling, turns, spacing=spacing)
                    else:
                        continue

                    # Apply position offsets
                    offset_geom = self._apply_position_offset(geom, x_offset, y_offset)
                    geometries.append(offset_geom)

                except AntennaGeometryError as e:
                    logger.warning(f"Geometry generation failed for {antenna_type}: {str(e)}")
                    return None

            # Combine geometries
            combined = self._combine_geometries(geometries)
            return combined

        except Exception as e:
            logger.error(f"Individual geometry generation error: {str(e)}")
            return None

    def _apply_position_offset(self, geometry: str, x_offset: float, y_offset: float) -> str:
        """Apply position offset to geometry coordinates."""
        try:
            lines = geometry.split('\n')
            modified_lines = []

            for line in lines:
                if not line.strip():
                    continue

                parts = line.split()
                if len(parts) >= 8 and parts[0] == 'GW':
                    # Apply offset to wire coordinates (x1,y1,x2,y2)
                    parts[3] = str(float(parts[3]) + x_offset)  # x1
                    parts[4] = str(float(parts[4]) + y_offset)  # y1
                    parts[6] = str(float(parts[6]) + x_offset)  # x2
                    parts[7] = str(float(parts[7]) + y_offset)  # y2

                modified_lines.append(' '.join(parts))

            return '\n'.join(modified_lines)

        except Exception as e:
            logger.error(f"Position offset application error: {str(e)}")
            return geometry

    def _combine_geometries(self, geometries: List[str]) -> str:
        """Combine multiple antenna geometries avoiding tag conflicts."""
        try:
            combined = []
            tag_offset = 0

            for geom in geometries:
                lines = geom.split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) > 1 and parts[0] in ['GW', 'SP']:
                            parts[1] = str(int(parts[1]) + tag_offset)
                        combined.append(' '.join(parts))

                tag_offset += 10  # Increment tag offset

            return '\n'.join(combined)

        except Exception as e:
            logger.error(f"Geometry combination error: {str(e)}")
            raise AntennaGeometryError(f"Failed to combine geometries: {str(e)}")

    def _calculate_size_penalty(self, geometry: str) -> float:
        """Calculate penalty for design size (prefer smaller designs)."""
        try:
            from design import GeometryValidation
            validation = GeometryValidation.check_bounds(geometry)

            if validation['within_bounds']:
                # Penalize designs close to boundaries (prefer 80% utilization)
                x_utilization = validation['max_x'] / 2.0  # Max x extent / substrate half-width
                y_utilization = validation['max_y'] / 1.0  # Max y extent / substrate half-height

                utilization = max(x_utilization, y_utilization)
                if utilization > 0.8:
                    return (utilization - 0.8) ** 2 * 10  # Quadratic penalty

            return 0.0

        except Exception as e:
            logger.warning(f"Size penalty calculation error: {str(e)}")
            return 5.0  # Moderate penalty for calculation failure

    def _evolve_population(self, fitness_scores: List[Tuple[Dict, float]]) -> List[Dict]:
        """Generate next population through selection and mutation."""
        try:
            new_population = []

            # Elitism - keep best individuals
            for i in range(self.elite_count):
                if i < len(fitness_scores):
                    new_population.append(fitness_scores[i][0].copy())

            # Fill rest through crossover and mutation
            while len(new_population) < self.population_size:
                # Tournament selection
                parent1 = self._tournament_selection(fitness_scores)
                parent2 = self._tournament_selection(fitness_scores)

                # Crossover
                child = self._crossover(parent1, parent2)

                # Mutation
                self._mutate(child)

                new_population.append(child)

            logger.info(f"Evolved new population of {len(new_population)} individuals")
            return new_population

        except Exception as e:
            logger.error(f"Population evolution error: {str(e)}")
            return self._initialize_population([100, 500, 1000])  # Fallback

    def _tournament_selection(self, fitness_scores: List[Tuple[Dict, float]]) -> Dict:
        """Tournament selection for parent selection."""
        tournament_size = 3
        tournament = np.random.choice(len(fitness_scores), tournament_size, replace=False)
        winners = [fitness_scores[i][0] for i in tournament]
        return winners[np.random.randint(len(winners))]  # Random winner from tournament

    def _crossover(self, parent1: Dict, parent2: Dict) -> Dict:
        """Crossover two parent individuals."""
        try:
            child = parent1.copy()

            # Crossover scaling factors
            if np.random.random() < 0.5:
                child['scaling_factors'] = parent2['scaling_factors'].copy()

            # Crossover position offsets
            crossover_point = np.random.randint(len(child['position_offsets']))
            child['position_offsets'][:crossover_point] = parent2['position_offsets'][:crossover_point]

            # Crossover coil parameters
            if child.get('coil_parameters') and parent2.get('coil_parameters'):
                if np.random.random() < 0.5:
                    child['coil_parameters'] = parent2['coil_parameters'].copy()

            return child

        except Exception as e:
            logger.error(f"Crossover error: {str(e)}")
            return parent1.copy()  # Return copy of first parent

    def _mutate(self, individual: Dict) -> None:
        """Mutate individual with small probability."""
        try:
            mutation_rate = 0.1

            # Mutate scaling factors
            for i in range(len(individual['scaling_factors'])):
                if np.random.random() < mutation_rate:
                    individual['scaling_factors'][i] *= np.random.uniform(0.9, 1.1)

            # Mutate position offsets
            for i in range(len(individual['position_offsets'])):
                if np.random.random() < mutation_rate:
                    individual['position_offsets'][i] += np.random.normal(0, 0.1)

            # Mutate coil parameters
            if individual.get('coil_parameters'):
                if np.random.random() < mutation_rate:
                    individual['coil_parameters']['turns'] = max(2, min(6,
                        individual['coil_parameters']['turns'] + np.random.randint(-1, 2)))
                if np.random.random() < mutation_rate:
                    individual['coil_parameters']['spacing'] *= np.random.uniform(0.95, 1.05)

        except Exception as e:
            logger.warning(f"Mutation error: {str(e)}")
            # Continue without mutation

    def _get_detailed_results(self, individual: Dict, frequencies: List[float]) -> Dict:
        """Get detailed simulation results for best individual."""
        try:
            geometry = self._generate_individual_geometry(individual, frequencies)
            if not geometry:
                raise OptimizationError("Failed to generate geometry for best individual")

            results = self.nec.run_simulation(geometry, frequencies)
            return results

        except Exception as e:
            logger.error(f"Detailed results extraction error: {str(e)}")
            return {}
