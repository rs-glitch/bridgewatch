# Tier 2 simulations

Every input is tagged stated, measured or assumed in `src/bridgewatch/sim/models.py`.

## Golden Gate Bridge, main span, one cable and its stiffening truss

- Dead-load cable pull 49,964 kip per cable; cable stress at the towers 77.0 ksi under full live load.

| Check | Model | Published | Source |
|---|---|---|---|
| Down at the quarter point, traffic tower to centre | 12.46 ft | 12.41 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |
| Up at the other quarter point, same traffic | 7.01 ft | 6.72 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |
| Down at the centre, whole main span loaded | 6.98 ft | 7.34 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |
| Deepest centre sag, traffic in the middle, 40°F warmer | 12.41 ft | 10.8 ft | Strauss, 1937 report |
| Highest centre lift, traffic at both ends, 40°F colder | 5.31 ft | 5.8 ft | Strauss, 1937 report |

- Live load only, worst anywhere: down 12.5 ft, up 7.1 ft; peak truss moment 40,205 kip-ft.

## George Washington Bridge (1931), main span, one cable and its stiffening floor

- Dead-load cable pull 37,885 kip per cable; cable stress at the towers 56.5 ksi under full live load.

| Check | Model | Published | Source |
|---|---|---|---|
| Down at the quarter point, traffic tower to centre | 5.60 ft | 5.88 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |
| Up at the other quarter point, same traffic | 3.94 ft | 3.54 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |
| Down at the centre, whole main span loaded | 2.20 ft | 2.92 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |

- Live load only, worst anywhere: down 5.6 ft, up 4.0 ft; peak floor moment 32 kip-ft.

## Tacoma Narrows Bridge (1940), main span, one cable and its stiffening girder

- Dead-load cable pull 12,039 kip per cable; cable stress at the towers 80.6 ksi under full live load.

| Check | Model | Published | Source |
|---|---|---|---|
| Down at the quarter point, traffic tower to centre | 10.99 ft | 10.95 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |
| Up at the other quarter point, same traffic | 2.66 ft | 2.74 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |
| Down at the centre, whole main span loaded | 10.41 ft | 10.5 ft | Ammann, von Kármán and Woodruff, 1941, Table 4 (normal temperature) |

- Live load only, worst anywhere: down 11.6 ft, up 3.1 ft; peak girder moment 2,107 kip-ft.

## Kelley Crossing Bridge (TX-31), one truss

| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |
|---|---|---|---|---|
| Dead load | L5-E6 (lower chord) | 5.6 | 22% | 0.39 |
| Dead + H10 (10-ton truck) | L5-E6 (lower chord) | 11.2 | 45% | 0.72 |
| Dead + H15 (15-ton truck) | L2-U3 (diagonal) | 15.5 | 62% | 0.89 |
| Dead + H20 (20-ton truck) | L2-U3 (diagonal) | 20.2 | 81% | 1.06 |
| Dead + 100 psf crowd | L5-E6 (lower chord) | 23.0 | 92% | 1.58 |

## Bridge L5245 (MN-133), one truss

| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |
|---|---|---|---|---|
| Dead load | L2-L3 (lower chord) | 7.1 | 24% | 0.22 |
| Dead + H10 (10-ton truck) | L2-L3 (lower chord) | 13.2 | 44% | 0.39 |
| Dead + H15 (15-ton truck) | L2-L3 (lower chord) | 16.2 | 54% | 0.48 |
| Dead + H20 (20-ton truck) | L1-U2 (diagonal) | 20.2 | 67% | 0.57 |
| Dead + 100 psf crowd | L2-L3 (lower chord) | 18.5 | 62% | 0.56 |

## Walnut Street Bridge (PA-412), one truss

| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |
|---|---|---|---|---|
| Dead load | L5-L6 (lower chord) | 5.7 | 23% | 0.81 |
| Dead + H10 (10-ton truck) | L8-U8 (vertical) | 6.8 | 27% | 0.99 |
| Dead + H15 (15-ton truck) | L8-U8 (vertical) | 7.9 | 32% | 1.08 |
| Dead + H20 (20-ton truck) | L8-U8 (vertical) | 9.0 | 36% | 1.18 |
| Dead + 100 psf crowd | L5-L6 (lower chord) | 15.1 | 61% | 2.14 |

## Upper Bridge at Slate Run (PA-460), one truss

| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |
|---|---|---|---|---|
| Dead load | L10-L11 (lower chord) | 5.7 | 23% | 0.92 |
| Dead + H10 (10-ton truck) | L10-L11 (lower chord) | 6.4 | 25% | 1.10 |
| Dead + H15 (15-ton truck) | L10-L11 (lower chord) | 6.7 | 27% | 1.19 |
| Dead + H20 (20-ton truck) | L10-L11 (lower chord) | 7.0 | 28% | 1.28 |
| Dead + 100 psf crowd | L10-L11 (lower chord) | 12.7 | 51% | 2.07 |

## Nicholson Township Lenticular Bridge (PA-468), one truss

| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |
|---|---|---|---|---|
| Dead load | M3-M4 (lower chord) | 3.3 | 13% | 0.33 |
| Dead + H10 (10-ton truck) | U2-M1 (diagonal) | 8.4 | 34% | 0.58 |
| Dead + H15 (15-ton truck) | U2-M1 (diagonal) | 14.0 | 56% | 0.70 |
| Dead + H20 (20-ton truck) | U2-M1 (diagonal) | 19.6 | 78% | 0.83 |
| Dead + 100 psf crowd | M3-M4 (lower chord) | 13.5 | 54% | 1.34 |

## Old Corinth Road Bridge (NY-292), one truss

| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |
|---|---|---|---|---|
| Dead load | U3-U4 (upper chord) | -3.7 | 15% | 0.42 |
| Dead + H10 (10-ton truck) | L1-U2 (diagonal) | 8.9 | 36% | 0.68 |
| Dead + H15 (15-ton truck) | L1-U2 (diagonal) | 13.4 | 54% | 0.81 |
| Dead + H20 (20-ton truck) | L1-U2 (diagonal) | 17.9 | 72% | 0.95 |
| Dead + 100 psf crowd | U3-U4 (upper chord) | -15.2 | 61% | 1.72 |

## Whetstone Creek Bridge (OH-90), one truss

| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |
|---|---|---|---|---|
| Dead load | L6-L7 (lower chord) | 4.0 | 16% | 0.50 |
| Dead + H10 (10-ton truck) | L3-U4 (diagonal) | 11.2 | 45% | 0.86 |
| Dead + H15 (15-ton truck) | L1-U2 (diagonal) | 17.2 | 69% | 1.05 |
| Dead + H20 (20-ton truck) | L1-U2 (diagonal) | 23.3 | 93% | 1.23 |
| Dead + 100 psf crowd | L6-L7 (lower chord) | 16.5 | 66% | 2.06 |

## Cooper's Tubular Arch Bridge (NY-291), one truss

| Load | Worst member | Stress (ksi) | Share of yield | Max deflection (in) |
|---|---|---|---|---|
| Dead load | L5-L6 (lower chord) | 1.9 | 7% | 0.12 |
| Dead + H10 (10-ton truck) | L1-U2 (diagonal) | 9.2 | 37% | 0.32 |
| Dead + H15 (15-ton truck) | L1-U2 (diagonal) | 13.8 | 55% | 0.42 |
| Dead + H20 (20-ton truck) | L1-U2 (diagonal) | 18.4 | 74% | 0.52 |
| Dead + 100 psf crowd | L5-L6 (lower chord) | 9.4 | 37% | 0.61 |
