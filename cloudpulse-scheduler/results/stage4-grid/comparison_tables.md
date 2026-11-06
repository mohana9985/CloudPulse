# Comparison tables — stage4-grid

Generated 2026-11-05T17:44:04+00:00 from `algorithm_comparison.csv` / `fcfs_vs_sjf.csv`. Values: mean ± sample SD across 10 seed(s). Times in simulated seconds. Rank (in brackets) is among the four primary algorithms only; FCFS is a control and is not ranked. Utilisation is simulated worker utilisation, not EC2 CPU.

> **Reading utilisation:** a higher mean utilisation is *not* automatically better. The same work keeps a slow worker busy for longer, so a policy that overloads slow workers (e.g. RR) can show the highest utilisation together with the worst waiting times. Read it together with waiting time and the per-worker chart.

## 100 tasks — underloaded (target utilisation 0.50)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 18.55 ± 12.25 [4] | 34.70 ± 12.44 [4] | 96.22 ± 52.88 [4] | 141.43 ± 47.80 [4] | 1059.5 ± 123.8 [4] | 0.0955 ± 0.0111 [4] | 51.3 ± 7.0 [1] | 22.0 ± 6.4 [4] |
| WRR | 9.23 ± 5.38 [3] | 23.46 ± 6.87 [3] | 46.05 ± 23.38 [3] | 92.93 ± 44.33 [3] | 1017.8 ± 116.4 [3] | 0.0995 ± 0.0122 [3] | 46.8 ± 5.8 [2] | 15.2 ± 5.3 [3] |
| LL | 2.31 ± 1.54 [2] | 16.03 ± 3.07 [2] | 13.64 ± 7.25 [2] | 25.67 ± 12.58 [1] | 993.3 ± 114.4 [1] | 0.1019 ± 0.0122 [1] | 46.4 ± 7.5 [4] | 0.3 ± 0.3 [2] |
| SJF | 1.78 ± 1.13 [1] | 15.50 ± 2.82 [1] | 10.62 ± 5.98 [1] | 27.33 ± 14.06 [2] | 993.3 ± 114.4 [1] | 0.1019 ± 0.0122 [1] | 46.4 ± 7.6 [3] | 0.0 ± 0.0 [1] |
| FCFS (control) | 2.27 ± 1.63 | 16.03 ± 3.25 | 13.47 ± 7.86 | 22.07 ± 8.40 | 993.3 ± 114.4 | 0.1019 ± 0.0122 | 46.5 ± 7.7 | 0.0 ± 0.0 |

## 100 tasks — nominal (target utilisation 0.85)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 50.77 ± 23.90 [4] | 66.92 ± 24.61 [4] | 197.51 ± 91.27 [4] | 253.49 ± 67.31 [4] | 814.7 ± 105.2 [4] | 0.1245 ± 0.0152 [4] | 66.8 ± 9.9 [4] | 24.7 ± 8.6 [4] |
| WRR | 27.26 ± 12.67 [3] | 41.49 ± 13.93 [3] | 91.70 ± 43.73 [3] | 139.25 ± 67.29 [3] | 683.8 ± 86.9 [3] | 0.1486 ± 0.0212 [3] | 69.5 ± 5.8 [3] | 18.1 ± 3.9 [3] |
| LL | 12.92 ± 8.73 [2] | 27.29 ± 9.91 [2] | 40.23 ± 22.88 [2] | 54.96 ± 24.98 [1] | 638.0 ± 84.0 [1] | 0.1594 ± 0.0228 [1] | 75.7 ± 10.4 [1] | 0.3 ± 0.2 [2] |
| SJF | 7.16 ± 4.71 [1] | 21.61 ± 6.05 [1] | 30.58 ± 18.07 [1] | 84.33 ± 57.35 [2] | 652.4 ± 63.3 [2] | 0.1546 ± 0.0153 [2] | 74.0 ± 8.5 [2] | 0.0 ± 0.0 [1] |
| FCFS (control) | 12.92 ± 9.28 | 27.29 ± 10.28 | 40.08 ± 24.16 | 50.57 ± 26.41 | 632.7 ± 78.1 | 0.1604 ± 0.0217 | 76.2 ± 10.2 | 0.0 ± 0.0 |

## 100 tasks — overloaded (target utilisation 1.20)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 83.76 ± 28.30 [4] | 99.90 ± 29.20 [4] | 289.50 ± 98.58 [4] | 354.25 ± 86.47 [4] | 762.3 ± 113.0 [4] | 0.1334 ± 0.0171 [4] | 71.5 ± 10.0 [4] | 24.7 ± 9.2 [4] |
| WRR | 58.38 ± 22.96 [3] | 72.60 ± 24.09 [3] | 161.85 ± 68.65 [3] | 200.82 ± 74.38 [2] | 600.4 ± 70.6 [3] | 0.1687 ± 0.0202 [3] | 79.0 ± 6.3 [3] | 16.5 ± 4.8 [3] |
| LL | 43.67 ± 20.65 [2] | 58.07 ± 21.68 [2] | 103.12 ± 51.55 [2] | 116.17 ± 54.97 [1] | 541.1 ± 64.7 [1] | 0.1873 ± 0.0234 [1] | 88.9 ± 7.4 [1] | 0.3 ± 0.3 [2] |
| SJF | 15.84 ± 6.58 [1] | 30.32 ± 7.94 [1] | 63.66 ± 32.30 [1] | 231.68 ± 107.83 [3] | 554.9 ± 76.2 [2] | 0.1834 ± 0.0264 [2] | 87.1 ± 6.2 [2] | 0.0 ± 0.0 [1] |
| FCFS (control) | 42.91 ± 21.19 | 57.30 ± 22.15 | 98.88 ± 50.42 | 112.47 ± 55.45 | 539.2 ± 63.8 | 0.1880 ± 0.0245 | 89.2 ± 7.9 | 0.0 ± 0.0 |

## 250 tasks — underloaded (target utilisation 0.50)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 29.46 ± 14.69 [4] | 45.62 ± 14.80 [4] | 163.54 ± 82.36 [4] | 260.24 ± 98.27 [4] | 2506.5 ± 184.4 [4] | 0.1003 ± 0.0078 [4] | 53.8 ± 3.4 [1] | 25.6 ± 8.0 [4] |
| WRR | 10.18 ± 2.70 [3] | 24.29 ± 3.79 [3] | 56.28 ± 8.73 [3] | 114.78 ± 32.50 [3] | 2386.9 ± 167.4 [2] | 0.1052 ± 0.0081 [2] | 49.3 ± 3.9 [2] | 16.5 ± 3.5 [3] |
| LL | 2.51 ± 0.85 [2] | 16.06 ± 1.88 [2] | 15.89 ± 3.80 [2] | 40.63 ± 14.95 [1] | 2388.7 ± 180.1 [3] | 0.1052 ± 0.0086 [3] | 47.4 ± 4.3 [4] | 0.3 ± 0.2 [2] |
| SJF | 1.86 ± 0.60 [1] | 15.45 ± 1.68 [1] | 11.89 ± 3.44 [1] | 41.98 ± 11.42 [2] | 2385.3 ± 168.3 [1] | 0.1053 ± 0.0080 [1] | 47.6 ± 4.4 [3] | 0.0 ± 0.0 [1] |
| FCFS (control) | 2.37 ± 0.84 | 16.01 ± 1.84 | 15.25 ± 5.04 | 32.54 ± 9.69 | 2385.6 ± 176.9 | 0.1054 ± 0.0085 | 47.7 ± 4.3 | 0.0 ± 0.0 |

## 250 tasks — nominal (target utilisation 0.85)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 122.11 ± 44.06 [4] | 138.27 ± 44.52 [4] | 503.44 ± 229.58 [4] | 615.96 ± 273.43 [4] | 1992.6 ± 250.2 [4] | 0.1273 ± 0.0165 [4] | 68.3 ± 7.7 [4] | 27.8 ± 9.0 [4] |
| WRR | 43.77 ± 20.61 [3] | 57.88 ± 21.49 [3] | 141.28 ± 54.77 [3] | 211.78 ± 75.98 [3] | 1500.1 ± 135.8 [3] | 0.1679 ± 0.0159 [3] | 78.5 ± 4.2 [3] | 14.7 ± 2.8 [3] |
| LL | 19.47 ± 12.21 [2] | 33.63 ± 13.20 [2] | 60.90 ± 22.92 [2] | 79.13 ± 27.04 [1] | 1453.0 ± 122.8 [1] | 0.1732 ± 0.0146 [1] | 81.4 ± 6.5 [1] | 0.2 ± 0.2 [2] |
| SJF | 9.88 ± 4.93 [1] | 24.11 ± 5.88 [1] | 44.71 ± 22.24 [1] | 144.23 ± 70.45 [2] | 1461.4 ± 121.5 [2] | 0.1721 ± 0.0142 [2] | 81.4 ± 6.3 [2] | 0.0 ± 0.0 [1] |
| FCFS (control) | 19.36 ± 12.18 | 33.51 ± 13.10 | 61.11 ± 22.44 | 74.40 ± 28.49 | 1441.7 ± 125.6 | 0.1746 ± 0.0153 | 82.1 ± 7.2 | 0.0 ± 0.0 |

## 250 tasks — overloaded (target utilisation 1.20)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 219.82 ± 51.36 [4] | 235.98 ± 52.00 [4] | 763.33 ± 254.28 [4] | 930.40 ± 288.65 [4] | 1927.2 ± 263.1 [4] | 0.1320 ± 0.0185 [4] | 70.8 ± 8.7 [4] | 27.2 ± 9.3 [4] |
| WRR | 134.40 ± 49.06 [3] | 148.50 ± 49.76 [3] | 311.24 ± 89.86 [3] | 390.96 ± 113.22 [2] | 1339.6 ± 130.6 [3] | 0.1882 ± 0.0184 [3] | 87.9 ± 4.2 [3] | 10.1 ± 3.8 [3] |
| LL | 112.98 ± 48.05 [2] | 127.19 ± 48.82 [2] | 225.80 ± 82.07 [2] | 249.95 ± 78.41 [1] | 1239.3 ± 110.3 [1] | 0.2032 ± 0.0183 [1] | 95.6 ± 2.4 [1] | 0.2 ± 0.3 [2] |
| SJF | 30.71 ± 10.80 [1] | 44.92 ± 11.63 [1] | 142.83 ± 86.12 [1] | 765.45 ± 257.83 [3] | 1256.8 ± 90.8 [2] | 0.1999 ± 0.0147 [2] | 94.2 ± 1.9 [2] | 0.0 ± 0.0 [1] |
| FCFS (control) | 112.56 ± 48.35 | 126.76 ± 49.13 | 220.43 ± 81.53 | 250.53 ± 83.45 | 1232.3 ± 104.0 | 0.2042 ± 0.0174 | 96.1 ± 2.2 | 0.0 ± 0.0 |

## 500 tasks — underloaded (target utilisation 0.50)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 54.25 ± 33.67 [4] | 71.11 ± 34.27 [4] | 294.12 ± 197.51 [4] | 435.04 ± 186.12 [4] | 4946.4 ± 298.6 [4] | 0.1014 ± 0.0063 [4] | 57.0 ± 3.7 [1] | 27.0 ± 6.8 [4] |
| WRR | 12.62 ± 2.78 [3] | 27.26 ± 3.09 [3] | 63.20 ± 8.90 [3] | 166.69 ± 66.08 [3] | 4733.0 ± 228.0 [3] | 0.1059 ± 0.0050 [3] | 51.6 ± 3.2 [2] | 16.4 ± 2.1 [3] |
| LL | 3.69 ± 1.88 [2] | 17.65 ± 2.24 [2] | 22.86 ± 10.23 [2] | 53.11 ± 12.76 [1] | 4723.3 ± 227.1 [1] | 0.1061 ± 0.0050 [2] | 49.4 ± 3.6 [4] | 0.3 ± 0.1 [2] |
| SJF | 2.46 ± 0.88 [1] | 16.56 ± 1.22 [1] | 14.38 ± 4.08 [1] | 74.71 ± 45.04 [2] | 4723.6 ± 233.5 [2] | 0.1061 ± 0.0052 [1] | 49.9 ± 3.5 [3] | 0.0 ± 0.0 [1] |
| FCFS (control) | 3.61 ± 1.98 | 17.70 ± 2.33 | 22.41 ± 11.36 | 47.92 ± 14.42 | 4725.4 ± 223.4 | 0.1060 ± 0.0049 | 49.8 ± 3.6 | 0.0 ± 0.0 |

## 500 tasks — nominal (target utilisation 0.85)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 266.74 ± 83.89 [4] | 283.60 ± 84.45 [4] | 1172.97 ± 505.36 [4] | 1389.33 ± 542.60 [4] | 4153.9 ± 478.9 [4] | 0.1218 ± 0.0138 [4] | 68.2 ± 5.8 [4] | 29.9 ± 6.1 [4] |
| WRR | 72.03 ± 33.15 [3] | 86.66 ± 33.42 [3] | 253.30 ± 116.49 [3] | 359.71 ± 115.08 [2] | 2979.0 ± 127.0 [3] | 0.1681 ± 0.0072 [3] | 82.0 ± 3.5 [3] | 13.4 ± 2.8 [3] |
| LL | 42.41 ± 35.97 [2] | 57.01 ± 36.27 [2] | 116.64 ± 81.06 [2] | 150.99 ± 77.54 [1] | 2876.0 ± 119.6 [1] | 0.1741 ± 0.0072 [1] | 84.8 ± 4.6 [1] | 0.3 ± 0.1 [2] |
| SJF | 15.15 ± 7.89 [1] | 29.82 ± 8.23 [1] | 56.38 ± 21.92 [1] | 502.67 ± 402.45 [3] | 2900.7 ± 118.3 [2] | 0.1726 ± 0.0072 [2] | 84.5 ± 4.4 [2] | 0.0 ± 0.0 [1] |
| FCFS (control) | 42.55 ± 36.16 | 57.19 ± 36.46 | 117.25 ± 80.88 | 143.60 ± 77.19 | 2871.6 ± 121.4 | 0.1744 ± 0.0074 | 85.1 ± 4.6 | 0.0 ± 0.0 |

## 500 tasks — overloaded (target utilisation 1.20)

| Algorithm | Average waiting time (s) | Average turnaround time (s) | 95th-percentile waiting time (s) | Maximum waiting time (s) | Makespan (s) | Throughput (tasks/s) | Mean worker utilisation (%) | Idle-while-waiting (% of worker-time) |
|---|---|---|---|---|---|---|---|---|
| RR | 477.06 ± 79.86 [4] | 493.91 ± 80.36 [4] | 1801.76 ± 498.48 [4] | 2110.92 ± 527.16 [4] | 4085.5 ± 493.4 [4] | 0.1240 ± 0.0148 [4] | 69.4 ± 6.4 [4] | 29.6 ± 6.2 [4] |
| WRR | 270.93 ± 58.35 [3] | 285.56 ± 58.48 [3] | 645.46 ± 153.10 [3] | 731.08 ± 178.92 [2] | 2685.1 ± 121.3 [3] | 0.1866 ± 0.0084 [3] | 90.9 ± 3.1 [3] | 7.7 ± 2.8 [3] |
| LL | 246.43 ± 57.01 [2] | 261.10 ± 57.22 [2] | 496.88 ± 148.83 [2] | 543.97 ± 148.20 [1] | 2499.5 ± 81.6 [1] | 0.2002 ± 0.0064 [1] | 97.8 ± 1.1 [1] | 0.2 ± 0.2 [2] |
| SJF | 58.44 ± 11.67 [1] | 73.15 ± 11.93 [1] | 262.38 ± 162.27 [1] | 1952.46 ± 214.31 [3] | 2540.2 ± 88.7 [2] | 0.1970 ± 0.0068 [2] | 96.5 ± 1.3 [2] | 0.0 ± 0.0 [1] |
| FCFS (control) | 245.74 ± 56.96 | 260.43 ± 57.18 | 491.19 ± 148.58 | 531.07 ± 151.31 | 2505.7 ± 88.3 | 0.1998 ± 0.0069 | 97.7 ± 1.2 | 0.0 ± 0.0 |

## FCFS (control) vs SJF — same central queue, same worker choice

Δ = SJF − FCFS per seed on the identical workload; negative = SJF lower. `SJF lower / higher` = number of seeds in each direction.

| Tasks | Load | Metric | FCFS | SJF | Δ mean ± SD | % change | SJF lower / higher |
|---|---|---|---|---|---|---|---|
| 100 | nominal | avg_waiting_time | 12.92 ± 9.28 | 7.16 ± 4.71 | -5.76 ± 4.88 | -44.6% | 10 / 0 |
| 100 | nominal | avg_turnaround_time | 27.29 ± 10.28 | 21.61 ± 6.05 | -5.68 ± 4.71 | -20.8% | 10 / 0 |
| 100 | nominal | p95_waiting_time | 40.08 ± 24.16 | 30.58 ± 18.07 | -9.50 ± 15.49 | -23.7% | 7 / 3 |
| 100 | nominal | max_waiting_time | 50.57 ± 26.41 | 84.33 ± 57.35 | 33.76 ± 34.20 | +66.8% | 1 / 9 |
| 100 | nominal | makespan | 632.66 ± 78.14 | 652.42 ± 63.32 | 19.75 ± 42.67 | +3.1% | 2 / 6 |
| 100 | nominal | small_avg_waiting_time | 13.49 ± 9.24 | 4.41 ± 2.57 | -9.08 ± 7.02 | -67.3% | 10 / 0 |
| 100 | nominal | medium_avg_waiting_time | 12.38 ± 10.46 | 8.75 ± 6.35 | -3.63 ± 4.88 | -29.3% | 6 / 4 |
| 100 | nominal | large_avg_waiting_time | 10.82 ± 7.00 | 18.28 ± 13.90 | 7.46 ± 8.15 | +68.9% | 2 / 8 |
| 100 | nominal | large_max_waiting_time | 33.27 ± 21.05 | 79.46 ± 62.32 | 46.18 ± 49.50 | +138.8% | 2 / 8 |
| 100 | overloaded | avg_waiting_time | 42.91 ± 21.19 | 15.84 ± 6.58 | -27.06 ± 15.01 | -63.1% | 10 / 0 |
| 100 | overloaded | avg_turnaround_time | 57.30 ± 22.15 | 30.32 ± 7.94 | -26.98 ± 15.00 | -47.1% | 10 / 0 |
| 100 | overloaded | p95_waiting_time | 98.88 ± 50.42 | 63.66 ± 32.30 | -35.22 ± 26.50 | -35.6% | 9 / 1 |
| 100 | overloaded | max_waiting_time | 112.47 ± 55.45 | 231.68 ± 107.83 | 119.21 ± 78.43 | +106.0% | 0 / 10 |
| 100 | overloaded | makespan | 539.24 ± 63.80 | 554.94 ± 76.24 | 15.70 ± 30.78 | +2.9% | 2 / 8 |
| 100 | overloaded | small_avg_waiting_time | 43.23 ± 21.28 | 5.72 ± 1.94 | -37.51 ± 20.37 | -86.8% | 10 / 0 |
| 100 | overloaded | medium_avg_waiting_time | 42.07 ± 22.33 | 15.93 ± 5.73 | -26.14 ± 17.54 | -62.1% | 9 / 1 |
| 100 | overloaded | large_avg_waiting_time | 41.14 ± 22.28 | 73.84 ± 34.45 | 32.71 ± 19.61 | +79.5% | 1 / 9 |
| 100 | overloaded | large_max_waiting_time | 90.32 ± 47.13 | 231.68 ± 107.83 | 141.36 ± 76.92 | +156.5% | 0 / 10 |
| 100 | underloaded | avg_waiting_time | 2.27 ± 1.63 | 1.78 ± 1.13 | -0.48 ± 0.56 | -21.3% | 8 / 1 |
| 100 | underloaded | avg_turnaround_time | 16.03 ± 3.25 | 15.50 ± 2.82 | -0.53 ± 0.53 | -3.3% | 9 / 0 |
| 100 | underloaded | p95_waiting_time | 13.47 ± 7.86 | 10.62 ± 5.98 | -2.85 ± 3.38 | -21.1% | 7 / 1 |
| 100 | underloaded | max_waiting_time | 22.07 ± 8.40 | 27.33 ± 14.06 | 5.26 ± 7.14 | +23.8% | 1 / 7 |
| 100 | underloaded | makespan | 993.28 ± 114.36 | 993.28 ± 114.36 | 0.00 ± 0.00 | +0.0% | 0 / 0 |
| 100 | underloaded | small_avg_waiting_time | 2.51 ± 1.79 | 1.67 ± 1.07 | -0.84 ± 0.96 | -33.5% | 8 / 1 |
| 100 | underloaded | medium_avg_waiting_time | 2.13 ± 1.96 | 2.16 ± 1.87 | 0.03 ± 0.46 | +1.3% | 2 / 6 |
| 100 | underloaded | large_avg_waiting_time | 1.31 ± 1.23 | 1.51 ± 1.75 | 0.20 ± 1.06 | +15.2% | 3 / 3 |
| 100 | underloaded | large_max_waiting_time | 8.98 ± 7.66 | 11.90 ± 14.06 | 2.92 ± 9.06 | +32.5% | 2 / 3 |
| 250 | nominal | avg_waiting_time | 19.36 ± 12.18 | 9.88 ± 4.93 | -9.48 ± 7.45 | -49.0% | 10 / 0 |
| 250 | nominal | avg_turnaround_time | 33.51 ± 13.10 | 24.11 ± 5.88 | -9.39 ± 7.43 | -28.0% | 10 / 0 |
| 250 | nominal | p95_waiting_time | 61.11 ± 22.44 | 44.71 ± 22.24 | -16.41 ± 14.82 | -26.8% | 10 / 0 |
| 250 | nominal | max_waiting_time | 74.40 ± 28.49 | 144.23 ± 70.45 | 69.84 ± 43.19 | +93.9% | 0 / 10 |
| 250 | nominal | makespan | 1441.70 ± 125.59 | 1461.44 ± 121.47 | 19.74 ± 36.70 | +1.4% | 3 / 5 |
| 250 | nominal | small_avg_waiting_time | 19.58 ± 12.23 | 5.38 ± 2.06 | -14.20 ± 11.02 | -72.5% | 10 / 0 |
| 250 | nominal | medium_avg_waiting_time | 19.33 ± 12.91 | 11.85 ± 4.72 | -7.48 ± 8.69 | -38.7% | 9 / 1 |
| 250 | nominal | large_avg_waiting_time | 18.09 ± 11.38 | 29.39 ± 19.87 | 11.30 ± 9.26 | +62.4% | 0 / 10 |
| 250 | nominal | large_max_waiting_time | 63.19 ± 22.65 | 142.11 ± 72.44 | 78.92 ± 51.19 | +124.9% | 0 / 10 |
| 250 | overloaded | avg_waiting_time | 112.56 ± 48.35 | 30.71 ± 10.80 | -81.86 ± 37.78 | -72.7% | 10 / 0 |
| 250 | overloaded | avg_turnaround_time | 126.76 ± 49.13 | 44.92 ± 11.63 | -81.84 ± 37.85 | -64.6% | 10 / 0 |
| 250 | overloaded | p95_waiting_time | 220.43 ± 81.53 | 142.83 ± 86.12 | -77.60 ± 26.75 | -35.2% | 10 / 0 |
| 250 | overloaded | max_waiting_time | 250.53 ± 83.45 | 765.45 ± 257.83 | 514.92 ± 219.29 | +205.5% | 0 / 10 |
| 250 | overloaded | makespan | 1232.30 ± 104.00 | 1256.84 ± 90.80 | 24.54 ± 31.04 | +2.0% | 1 / 9 |
| 250 | overloaded | small_avg_waiting_time | 113.05 ± 48.11 | 6.67 ± 1.35 | -106.38 ± 48.00 | -94.1% | 10 / 0 |
| 250 | overloaded | medium_avg_waiting_time | 112.79 ± 51.38 | 21.77 ± 3.99 | -91.01 ± 49.97 | -80.7% | 10 / 0 |
| 250 | overloaded | large_avg_waiting_time | 108.26 ± 43.83 | 198.55 ± 73.32 | 90.29 ± 33.65 | +83.4% | 0 / 10 |
| 250 | overloaded | large_max_waiting_time | 230.27 ± 81.13 | 765.45 ± 257.83 | 535.18 ± 210.89 | +232.4% | 0 / 10 |
| 250 | underloaded | avg_waiting_time | 2.37 ± 0.84 | 1.86 ± 0.60 | -0.51 ± 0.32 | -21.5% | 10 / 0 |
| 250 | underloaded | avg_turnaround_time | 16.01 ± 1.84 | 15.45 ± 1.68 | -0.55 ± 0.32 | -3.5% | 10 / 0 |
| 250 | underloaded | p95_waiting_time | 15.25 ± 5.04 | 11.89 ± 3.44 | -3.37 ± 2.56 | -22.1% | 9 / 1 |
| 250 | underloaded | max_waiting_time | 32.54 ± 9.69 | 41.98 ± 11.42 | 9.45 ± 10.75 | +29.0% | 2 / 8 |
| 250 | underloaded | makespan | 2385.59 ± 176.92 | 2385.30 ± 168.30 | -0.29 ± 10.03 | -0.0% | 2 / 1 |
| 250 | underloaded | small_avg_waiting_time | 2.45 ± 0.88 | 1.52 ± 0.36 | -0.94 ± 0.66 | -38.2% | 10 / 0 |
| 250 | underloaded | medium_avg_waiting_time | 2.32 ± 0.96 | 2.41 ± 1.21 | 0.09 ± 0.49 | +4.0% | 4 / 6 |
| 250 | underloaded | large_avg_waiting_time | 2.09 ± 1.26 | 2.36 ± 1.43 | 0.27 ± 0.60 | +12.9% | 5 / 5 |
| 250 | underloaded | large_max_waiting_time | 21.47 ± 10.11 | 24.47 ± 12.22 | 3.00 ± 9.07 | +14.0% | 5 / 5 |
| 500 | nominal | avg_waiting_time | 42.55 ± 36.16 | 15.15 ± 7.89 | -27.40 ± 28.42 | -64.4% | 10 / 0 |
| 500 | nominal | avg_turnaround_time | 57.19 ± 36.46 | 29.82 ± 8.23 | -27.36 ± 28.41 | -47.8% | 10 / 0 |
| 500 | nominal | p95_waiting_time | 117.25 ± 80.88 | 56.38 ± 21.92 | -60.87 ± 60.81 | -51.9% | 10 / 0 |
| 500 | nominal | max_waiting_time | 143.60 ± 77.19 | 502.67 ± 402.45 | 359.07 ± 328.42 | +250.1% | 0 / 10 |
| 500 | nominal | makespan | 2871.60 ± 121.39 | 2900.69 ± 118.35 | 29.09 ± 34.85 | +1.0% | 1 / 8 |
| 500 | nominal | small_avg_waiting_time | 42.19 ± 35.04 | 5.85 ± 1.07 | -36.34 ± 35.19 | -86.1% | 10 / 0 |
| 500 | nominal | medium_avg_waiting_time | 43.54 ± 36.98 | 13.59 ± 3.96 | -29.96 ± 34.83 | -68.8% | 10 / 0 |
| 500 | nominal | large_avg_waiting_time | 41.53 ± 41.13 | 73.45 ± 73.16 | 31.92 ± 32.57 | +76.9% | 0 / 10 |
| 500 | nominal | large_max_waiting_time | 125.70 ± 82.36 | 502.67 ± 402.45 | 376.97 ± 325.49 | +299.9% | 0 / 10 |
| 500 | overloaded | avg_waiting_time | 245.74 ± 56.96 | 58.44 ± 11.67 | -187.30 ± 45.86 | -76.2% | 10 / 0 |
| 500 | overloaded | avg_turnaround_time | 260.43 ± 57.18 | 73.15 ± 11.93 | -187.28 ± 45.89 | -71.9% | 10 / 0 |
| 500 | overloaded | p95_waiting_time | 491.19 ± 148.58 | 262.38 ± 162.27 | -228.82 ± 103.35 | -46.6% | 10 / 0 |
| 500 | overloaded | max_waiting_time | 531.07 ± 151.31 | 1952.46 ± 214.31 | 1421.39 ± 320.74 | +267.6% | 0 / 10 |
| 500 | overloaded | makespan | 2505.74 ± 88.29 | 2540.23 ± 88.72 | 34.50 ± 28.91 | +1.4% | 2 / 8 |
| 500 | overloaded | small_avg_waiting_time | 244.82 ± 56.96 | 6.98 ± 0.93 | -237.84 ± 57.27 | -97.1% | 10 / 0 |
| 500 | overloaded | medium_avg_waiting_time | 247.69 ± 63.04 | 25.01 ± 2.12 | -222.67 ± 61.99 | -89.9% | 10 / 0 |
| 500 | overloaded | large_avg_waiting_time | 243.22 ± 49.75 | 452.49 ± 125.07 | 209.27 ± 85.40 | +86.0% | 0 / 10 |
| 500 | overloaded | large_max_waiting_time | 522.31 ± 151.13 | 1952.46 ± 214.31 | 1430.15 ± 318.63 | +273.8% | 0 / 10 |
| 500 | underloaded | avg_waiting_time | 3.61 ± 1.98 | 2.46 ± 0.88 | -1.15 ± 1.16 | -31.8% | 10 / 0 |
| 500 | underloaded | avg_turnaround_time | 17.70 ± 2.33 | 16.56 ± 1.22 | -1.14 ± 1.19 | -6.4% | 10 / 0 |
| 500 | underloaded | p95_waiting_time | 22.41 ± 11.36 | 14.38 ± 4.08 | -8.03 ± 8.47 | -35.8% | 10 / 0 |
| 500 | underloaded | max_waiting_time | 47.92 ± 14.42 | 74.71 ± 45.04 | 26.80 ± 31.89 | +55.9% | 0 / 10 |
| 500 | underloaded | makespan | 4725.37 ± 223.38 | 4723.56 ± 233.52 | -1.81 ± 18.88 | -0.0% | 1 / 1 |
| 500 | underloaded | small_avg_waiting_time | 3.50 ± 1.77 | 1.69 ± 0.40 | -1.81 ± 1.55 | -51.8% | 10 / 0 |
| 500 | underloaded | medium_avg_waiting_time | 3.80 ± 2.27 | 3.01 ± 0.94 | -0.80 ± 1.56 | -21.0% | 5 / 5 |
| 500 | underloaded | large_avg_waiting_time | 3.61 ± 2.61 | 5.24 ± 4.68 | 1.63 ± 2.11 | +45.1% | 2 / 8 |
| 500 | underloaded | large_max_waiting_time | 35.02 ± 13.62 | 66.54 ± 51.69 | 31.52 ± 40.19 | +90.0% | 1 / 8 |
