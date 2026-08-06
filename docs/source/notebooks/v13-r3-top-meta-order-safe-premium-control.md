# v13-r3-top-meta-order-safe-premium-control

> Extracted by `analysis/nb_extract.py` from `notebooks/v13-r3-top-meta-order-safe-premium-control.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

# V13-R3 | Order-Safe Premium Control for Top-Meta Matchups

### A complete high-score Kaggriculture agent validated against replay-derived top-route proxies and current public frontier strategies

V13-R3 is a complete Kaggriculture agent implemented independently in a clean-room workflow. No source code from a public notebook was imported, forked, or reused. Its production schedule and market prior were reconstructed from public replay observations, then implemented and validated locally.

The agent combines a complete 719-turn production schedule, actor-local recovery, inventory-safe market execution, and an order-safe premium controller. The controller targets a narrow but important top-meta failure mode: when two farms follow highly similar schedules, both may send the same premium product into the shared market at nearly the same time. V13-R3 can move a bounded part of its next planned `SELL` one turn earlier, then repay that quantity on the following turn.

Frozen paired-seat results include:

- **31 wins / 1 loss** against the exact public V21.1 artifact;
- **16 / 16 paired seeds positive** in that panel;
- a **91 / 5** result across six replay-derived top-route proxies;
- a **96 / 0** regression result across six public strong-route controls.

These are local results under `kaggle-environments==1.32.4`, not a promise of future leaderboard performance. This notebook recomputes every displayed metric and reconstructs the exact 28,715-byte `main.py` at the end.

## cell [1] — code

```python
from io import StringIO
import json
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

plt.rcParams["figure.dpi"] = 125
plt.rcParams["axes.unicode_minus"] = False

TEAL = "#0F766E"
TEAL_LIGHT = "#5EEAD4"
ORANGE = "#EA580C"
SLATE = "#64748B"
LIGHT = "#E2E8F0"
DARK = "#0F172A"

AGENT_SHA256 = "6f52902081fed08bb5da08d575b796437e645c5320662b448b81eb079f185cfb"
V21_SHA256 = "d9dc24ce5429ec628ead0621a160bee90725350683d7dfcc4686fcaf511f3aab"
ENGINE_VERSION = "1.32.4"

gold_games = pd.read_csv(StringIO(r"""candidate,margin,my_reward,my_status,opp_reward,opp_status,opponent,result,seat,seed
v13r3_order_safe,11922.0,134478.0,DONE,122556.0,DONE,Top-route replay proxy A,win,0,87703
v13r3_order_safe,11922.0,134478.0,DONE,122556.0,DONE,Top-route replay proxy A,win,1,87703
v13r3_order_safe,1509.0,86257.0,DONE,84748.0,DONE,Top-route replay proxy A,win,0,87721
v13r3_order_safe,803.0,85882.0,DONE,85079.0,DONE,Top-route replay proxy A,win,1,87721
v13r3_order_safe,98.0,91400.0,DONE,91302.0,DONE,Top-route replay proxy A,win,0,87739
v13r3_order_safe,-995.0,90954.0,DONE,91949.0,DONE,Top-route replay proxy A,loss,1,87739
v13r3_order_safe,10651.0,153454.0,DONE,142803.0,DONE,Top-route replay proxy A,win,0,87763
v13r3_order_safe,9735.0,152546.0,DONE,142811.0,DONE,Top-route replay proxy A,win,1,87763
v13r3_order_safe,8028.0,138166.0,DONE,130138.0,DONE,Top-route replay proxy A,win,0,87781
v13r3_order_safe,8028.0,138166.0,DONE,130138.0,DONE,Top-route replay proxy A,win,1,87781
v13r3_order_safe,10355.0,153589.0,DONE,143234.0,DONE,Top-route replay proxy A,win,0,87809
v13r3_order_safe,10355.0,153589.0,DONE,143234.0,DONE,Top-route replay proxy A,win,1,87809
v13r3_order_safe,10646.0,153423.0,DONE,142777.0,DONE,Top-route replay proxy A,win,0,87827
v13r3_order_safe,11740.0,153631.0,DONE,141891.0,DONE,Top-route replay proxy A,win,1,87827
v13r3_order_safe,120.0,137586.0,DONE,137466.0,DONE,Top-route replay proxy A,win,0,87851
v13r3_order_safe,120.0,137586.0,DONE,137466.0,DONE,Top-route replay proxy A,win,1,87851
v13r3_order_safe,9308.0,130810.0,DONE,121502.0,DONE,Top-route replay proxy B,win,0,87703
v13r3_order_safe,9308.0,130810.0,DONE,121502.0,DONE,Top-route replay proxy B,win,1,87703
v13r3_order_safe,4497.0,103681.0,DONE,99184.0,DONE,Top-route replay proxy B,win,0,87721
v13r3_order_safe,4497.0,103681.0,DONE,99184.0,DONE,Top-route replay proxy B,win,1,87721
v13r3_order_safe,-267.0,81311.0,DONE,81578.0,DONE,Top-route replay proxy B,loss,0,87739
v13r3_order_safe,-549.0,81207.0,DONE,81756.0,DONE,Top-route replay proxy B,loss,1,87739
v13r3_order_safe,5799.0,147357.0,DONE,141558.0,DONE,Top-route replay proxy B,win,0,87763
v13r3_order_safe,6551.0,147808.0,DONE,141257.0,DONE,Top-route replay proxy B,win,1,87763
v13r3_order_safe,7548.0,140366.0,DONE,132818.0,DONE,Top-route replay proxy B,win,0,87781
v13r3_order_safe,7548.0,140366.0,DONE,132818.0,DONE,Top-route replay proxy B,win,1,87781
v13r3_order_safe,9709.0,150590.0,DONE,140881.0,DONE,Top-route replay proxy B,win,0,87809
v13r3_order_safe,9709.0,150590.0,DONE,140881.0,DONE,Top-route replay proxy B,win,1,87809
v13r3_order_safe,4454.0,154844.0,DONE,150390.0,DONE,Top-route replay proxy B,win,0,87827
v13r3_order_safe,6467.0,155731.0,DONE,149264.0,DONE,Top-route replay proxy B,win,1,87827
v13r3_order_safe,2125.0,130285.0,DONE,128160.0,DONE,Top-route replay proxy B,win,0,87851
v13r3_order_safe,2330.0,130293.0,DONE,127963.0,DONE,Top-route replay proxy B,win,1,87851
v13r3_order_safe,2487.0,117477.0,DONE,114990.0,DONE,Top-route replay proxy C,win,0,87703
v13r3_order_safe,2487.0,117477.0,DONE,114990.0,DONE,Top-route replay proxy C,win,1,87703
v13r3_order_safe,698.0,82791.0,DONE,82093.0,DONE,Top-route replay proxy C,win,0,87721
v13r3_order_safe,-389.0,83191.0,DONE,83580.0,DONE,Top-route replay proxy C,loss,1,87721
v13r3_order_safe,861.0,91128.0,DONE,90267.0,DONE,Top-route replay proxy C,win,0,87739
v13r3_order_safe,-188.0,90685.0,DONE,90873.0,DONE,Top-route replay proxy C,loss,1,87739
v13r3_order_safe,1446.0,161856.0,DONE,160410.0,DONE,Top-route replay proxy C,win,0,87763
v13r3_order_safe,2492.0,162018.0,DONE,159526.0,DONE,Top-route replay proxy C,win,1,87763
v13r3_order_safe,4679.0,145750.0,DONE,141071.0,DONE,Top-route replay proxy C,win,0,87781
v13r3_order_safe,4287.0,145596.0,DONE,141309.0,DONE,Top-route replay proxy C,win,1,87781
v13r3_order_safe,5770.0,146690.0,DONE,140920.0,DONE,Top-route replay proxy C,win,0,87809
v13r3_order_safe,5770.0,146690.0,DONE,140920.0,DONE,Top-route replay proxy C,win,1,87809
v13r3_order_safe,2199.0,132653.0,DONE,130454.0,DONE,Top-route replay proxy C,win,0,87827
v13r3_order_safe,3758.0,133394.0,DONE,129636.0,DONE,Top-route replay proxy C,win,1,87827
v13r3_order_safe,1344.0,137986.0,DONE,136642.0,DONE,Top-route replay proxy C,win,0,87851
v13r3_order_safe,1344.0,137986.0,DONE,136642.0,DONE,Top-route replay proxy C,win,1,87851
v13r3_order_safe,7515.0,128314.0,DONE,120799.0,DONE,Top-route replay proxy D,win,0,87703
v13r3_order_safe,7515.0,128314.0,DONE,120799.0,DONE,Top-route replay proxy D,win,1,87703
v13r3_order_safe,4895.0,100483.0,DONE,95588.0,DONE,Top-route replay proxy D,win,0,87721
v13r3_order_safe,3954.0,100014.0,DONE,96060.0,DONE,Top-route replay proxy D,win,1,87721
v13r3_order_safe,1555.0,82940.0,DONE,81385.0,DONE,Top-route replay proxy D,win,0,87739
v13r3_order_safe,1141.0,82733.0,DONE,81592.0,DONE,Top-route replay proxy D,win,1,87739
v13r3_order_safe,5927.0,164323.0,DONE,158396.0,DONE,Top-route replay proxy D,win,0,87763
v13r3_order_safe,6077.0,164473.0,DONE,158396.0,DONE,Top-route replay proxy D,win,1,87763
v13r3_order_safe,6328.0,160484.0,DONE,154156.0,DONE,Top-route replay proxy D,win,0,87781
v13r3_order_safe,6328.0,160484.0,DONE,154156.0,DONE,Top-route replay proxy D,win,1,87781
v13r3_order_safe,6824.0,147340.0,DONE,140516.0,DONE,Top-route replay proxy D,win,0,87809
v13r3_order_safe,6824.0,147340.0,DONE,140516.0,DONE,Top-route replay proxy D,win,1,87809
v13r3_order_safe,6817.0,138755.0,DONE,131938.0,DONE,Top-route replay proxy D,win,0,87827
v13r3_order_safe,8539.0,139616.0,DONE,131077.0,DONE,Top-route replay proxy D,win,1,87827
v13r3_order_safe,1993.0,127724.0,DONE,125731.0,DONE,Top-route replay proxy D,win,0,87851
v13r3_order_safe,1993.0,127724.0,DONE,125731.0,DONE,Top-route replay proxy D,win,1,87851
v13r3_order_safe,2516.0,126713.0,DONE,124197.0,DONE,Top-route replay proxy E,win,0,87703
v13r3_order_safe,2516.0,126713.0,DONE,124197.0,DONE,Top-route replay proxy E,win,1,87703
v13r3_order_safe,1592.0,83988.0,DONE,82396.0,DONE,Top-route replay proxy E,win,0,87721
v13r3_order_safe,388.0,83869.0,DONE,83481.0,DONE,Top-route replay proxy E,win,1,87721
v13r3_order_safe,2756.0,92360.0,DONE,89604.0,DONE,Top-route replay proxy E,win,0,87739
v13r3_order_safe,1746.0,91987.0,DONE,90241.0,DONE,Top-route replay proxy E,win,1,87739
v13r3_order_safe,4859.0,162601.0,DONE,157742.0,DONE,Top-route replay proxy E,win,0,87763
v13r3_order_safe,5009.0,162751.0,DONE,157742.0,DONE,Top-route replay proxy E,win,1,87763
v13r3_order_safe,1880.0,131599.0,DONE,129719.0,DONE,Top-route replay proxy E,win,0,87781
v13r3_order_safe,1880.0,131599.0,DONE,129719.0,DONE,Top-route replay proxy E,win,1,87781
v13r3_order_safe,4678.0,137384.0,DONE,132706.0,DONE,Top-route replay proxy E,win,0,87809
v13r3_order_safe,4678.0,137384.0,DONE,132706.0,DONE,Top-route replay proxy E,win,1,87809
v13r3_order_safe,620.0,152197.0,DONE,151577.0,DONE,Top-route replay proxy E,win,0,87827
v13r3_order_safe,3562.0,153502.0,DONE,149940.0,DONE,Top-route replay proxy E,win,1,87827
v13r3_order_safe,3218.0,138895.0,DONE,135677.0,DONE,Top-route replay proxy E,win,0,87851
v13r3_order_safe,3218.0,138895.0,DONE,135677.0,DONE,Top-route replay proxy E,win,1,87851
v13r3_order_safe,4997.0,111699.0,DONE,106702.0,DONE,Top-route replay proxy F,win,0,87703
v13r3_order_safe,4997.0,111699.0,DONE,106702.0,DONE,Top-route replay proxy F,win,1,87703
v13r3_order_safe,4705.0,100522.0,DONE,95817.0,DONE,Top-route replay proxy F,win,0,87721
v13r3_order_safe,3609.0,100088.0,DONE,96479.0,DONE,Top-route replay proxy F,win,1,87721
v13r3_order_safe,4187.0,84321.0,DONE,80134.0,DONE,Top-route replay proxy F,win,0,87739
v13r3_order_safe,3850.0,84152.0,DONE,80302.0,DONE,Top-route replay proxy F,win,1,87739
v13r3_order_safe,2668.0,158731.0,DONE,156063.0,DONE,Top-route replay proxy F,win,0,87763
v13r3_order_safe,2980.0,158887.0,DONE,155907.0,DONE,Top-route replay proxy F,win,1,87763
v13r3_order_safe,4017.0,147202.0,DONE,143185.0,DONE,Top-route replay proxy F,win,0,87781
v13r3_order_safe,3821.0,147104.0,DONE,143283.0,DONE,Top-route replay proxy F,win,1,87781
v13r3_order_safe,4306.0,146028.0,DONE,141722.0,DONE,Top-route replay proxy F,win,0,87809
v13r3_order_safe,4306.0,146028.0,DONE,141722.0,DONE,Top-route replay proxy F,win,1,87809
v13r3_order_safe,1616.0,149199.0,DONE,147583.0,DONE,Top-route replay proxy F,win,0,87827
v13r3_order_safe,3660.0,150221.0,DONE,146561.0,DONE,Top-route replay proxy F,win,1,87827
v13r3_order_safe,2924.0,128538.0,DONE,125614.0,DONE,Top-route replay proxy F,win,0,87851
v13r3_order_safe,2924.0,128538.0,DONE,125614.0,DONE,Top-route replay proxy F,win,1,87851
"""))
public_games = pd.read_csv(StringIO(r"""candidate,margin,my_reward,my_status,opp_reward,opp_status,opponent,result,seat,seed
v13r3_order_safe,11867.0,153232.0,DONE,141365.0,DONE,Public strong-route control A,win,0,87703
v13r3_order_safe,11867.0,153232.0,DONE,141365.0,DONE,Public strong-route control A,win,1,87703
v13r3_order_safe,6964.0,126001.0,DONE,119037.0,DONE,Public strong-route control A,win,0,87721
v13r3_order_safe,5730.0,105138.0,DONE,99408.0,DONE,Public strong-route control A,win,1,87721
v13r3_order_safe,8423.0,144970.0,DONE,136547.0,DONE,Public strong-route control A,win,0,87739
v13r3_order_safe,7141.0,138109.0,DONE,130968.0,DONE,Public strong-route control A,win,1,87739
v13r3_order_safe,10117.0,106745.0,DONE,96628.0,DONE,Public strong-route control A,win,0,87763
v13r3_order_safe,10278.0,106901.0,DONE,96623.0,DONE,Public strong-route control A,win,1,87763
v13r3_order_safe,6371.0,103181.0,DONE,96810.0,DONE,Public strong-route control A,win,0,87781
v13r3_order_safe,6278.0,103174.0,DONE,96896.0,DONE,Public strong-route control A,win,1,87781
v13r3_order_safe,13354.0,135665.0,DONE,122311.0,DONE,Public strong-route control A,win,0,87809
v13r3_order_safe,13354.0,135665.0,DONE,122311.0,DONE,Public strong-route control A,win,1,87809
v13r3_order_safe,4930.0,106040.0,DONE,101110.0,DONE,Public strong-route control A,win,0,87827
v13r3_order_safe,7551.0,103218.0,DONE,95667.0,DONE,Public strong-route control A,win,1,87827
v13r3_order_safe,6065.0,113352.0,DONE,107287.0,DONE,Public strong-route control A,win,0,87851
v13r3_order_safe,6065.0,113352.0,DONE,107287.0,DONE,Public strong-route control A,win,1,87851
v13r3_order_safe,14804.0,155224.0,DONE,140420.0,DONE,Public strong-route control B,win,0,87703
v13r3_order_safe,14804.0,155224.0,DONE,140420.0,DONE,Public strong-route control B,win,1,87703
v13r3_order_safe,11100.0,130002.0,DONE,118902.0,DONE,Public strong-route control B,win,0,87721
v13r3_order_safe,8980.0,106969.0,DONE,97989.0,DONE,Public strong-route control B,win,1,87721
v13r3_order_safe,14344.0,147560.0,DONE,133216.0,DONE,Public strong-route control B,win,0,87739
v13r3_order_safe,12975.0,140382.0,DONE,127407.0,DONE,Public strong-route control B,win,1,87739
v13r3_order_safe,9680.0,108323.0,DONE,98643.0,DONE,Public strong-route control B,win,0,87763
v13r3_order_safe,10017.0,108476.0,DONE,98459.0,DONE,Public strong-route control B,win,1,87763
v13r3_order_safe,7712.0,103813.0,DONE,96101.0,DONE,Public strong-route control B,win,0,87781
v13r3_order_safe,7712.0,103813.0,DONE,96101.0,DONE,Public strong-route control B,win,1,87781
v13r3_order_safe,12459.0,137691.0,DONE,125232.0,DONE,Public strong-route control B,win,0,87809
v13r3_order_safe,12459.0,137691.0,DONE,125232.0,DONE,Public strong-route control B,win,1,87809
v13r3_order_safe,8891.0,109864.0,DONE,100973.0,DONE,Public strong-route control B,win,0,87827
v13r3_order_safe,10477.0,104725.0,DONE,94248.0,DONE,Public strong-route control B,win,1,87827
v13r3_order_safe,7824.0,115780.0,DONE,107956.0,DONE,Public strong-route control B,win,0,87851
v13r3_order_safe,7947.0,115775.0,DONE,107828.0,DONE,Public strong-route control B,win,1,87851
v13r3_order_safe,13053.0,151006.0,DONE,137953.0,DONE,Public strong-route control C,win,0,87703
v13r3_order_safe,13053.0,151006.0,DONE,137953.0,DONE,Public strong-route control C,win,1,87703
v13r3_order_safe,18873.0,132442.0,DONE,113569.0,DONE,Public strong-route control C,win,0,87721
v13r3_order_safe,16075.0,143237.0,DONE,127162.0,DONE,Public strong-route control C,win,1,87721
v13r3_order_safe,11836.0,126495.0,DONE,114659.0,DONE,Public strong-route control C,win,0,87739
v13r3_order_safe,11629.0,126395.0,DONE,114766.0,DONE,Public strong-route control C,win,1,87739
v13r3_order_safe,11136.0,81866.0,DONE,70730.0,DONE,Public strong-route control C,win,0,87763
v13r3_order_safe,10143.0,81408.0,DONE,71265.0,DONE,Public strong-route control C,win,1,87763
v13r3_order_safe,11584.0,97510.0,DONE,85926.0,DONE,Public strong-route control C,win,0,87781
v13r3_order_safe,11584.0,97510.0,DONE,85926.0,DONE,Public strong-route control C,win,1,87781
v13r3_order_safe,13842.0,119652.0,DONE,105810.0,DONE,Public strong-route control C,win,0,87809
v13r3_order_safe,13842.0,119652.0,DONE,105810.0,DONE,Public strong-route control C,win,1,87809
v13r3_order_safe,7001.0,97828.0,DONE,90827.0,DONE,Public strong-route control C,win,0,87827
v13r3_order_safe,14136.0,110515.0,DONE,96379.0,DONE,Public strong-route control C,win,1,87827
v13r3_order_safe,14748.0,153517.0,DONE,138769.0,DONE,Public strong-route control C,win,0,87851
v13r3_order_safe,14989.0,153518.0,DONE,138529.0,DONE,Public strong-route control C,win,1,87851
v13r3_order_safe,14804.0,155224.0,DONE,140420.0,DONE,Public strong-route control D,win,0,87703
v13r3_order_safe,14804.0,155224.0,DONE,140420.0,DONE,Public strong-route control D,win,1,87703
v13r3_order_safe,11100.0,130002.0,DONE,118902.0,DONE,Public strong-route control D,win,0,87721
v13r3_order_safe,8980.0,106969.0,DONE,97989.0,DONE,Public strong-route control D,win,1,87721
v13r3_order_safe,14344.0,147560.0,DONE,133216.0,DONE,Public strong-route control D,win,0,87739
v13r3_order_safe,12975.0,140382.0,DONE,127407.0,DONE,Public strong-route control D,win,1,87739
v13r3_order_safe,9680.0,108323.0,DONE,98643.0,DONE,Public strong-route control D,win,0,87763
v13r3_order_safe,10017.0,108476.0,DONE,98459.0,DONE,Public strong-route control D,win,1,87763
v13r3_order_safe,7712.0,103813.0,DONE,96101.0,DONE,Public strong-route control D,win,0,87781
v13r3_order_safe,7712.0,103813.0,DONE,96101.0,DONE,Public strong-route control D,win,1,87781
v13r3_order_safe,12459.0,137691.0,DONE,125232.0,DONE,Public strong-route control D,win,0,87809
v13r3_order_safe,12459.0,137691.0,DONE,125232.0,DONE,Public strong-route control D,win,1,87809
v13r3_order_safe,8891.0,109864.0,DONE,100973.0,DONE,Public strong-route control D,win,0,87827
v13r3_order_safe,10477.0,104725.0,DONE,94248.0,DONE,Public strong-route control D,win,1,87827
v13r3_order_safe,7824.0,115780.0,DONE,107956.0,DONE,Public strong-route control D,win,0,87851
v13r3_order_safe,7947.0,115775.0,DONE,107828.0,DONE,Public strong-route control D,win,1,87851
v13r3_order_safe,10292.0,149604.0,DONE,139312.0,DONE,Public strong-route control E,win,0,87703
v13r3_order_safe,10292.0,149604.0,DONE,139312.0,DONE,Public strong-route control E,win,1,87703
v13r3_order_safe,16052.0,131143.0,DONE,115091.0,DONE,Public strong-route control E,win,0,87721
v13r3_order_safe,13226.0,141935.0,DONE,128709.0,DONE,Public strong-route control E,win,1,87721
v13r3_order_safe,9004.0,125062.0,DONE,116058.0,DONE,Public strong-route control E,win,0,87739
v13r3_order_safe,8799.0,124963.0,DONE,116164.0,DONE,Public strong-route control E,win,1,87739
v13r3_order_safe,6821.0,79693.0,DONE,72872.0,DONE,Public strong-route control E,win,0,87763
v13r3_order_safe,5740.0,79172.0,DONE,73432.0,DONE,Public strong-route control E,win,1,87763
v13r3_order_safe,6735.0,95051.0,DONE,88316.0,DONE,Public strong-route control E,win,0,87781
v13r3_order_safe,6735.0,95051.0,DONE,88316.0,DONE,Public strong-route control E,win,1,87781
v13r3_order_safe,9098.0,117286.0,DONE,108188.0,DONE,Public strong-route control E,win,0,87809
v13r3_order_safe,9098.0,117286.0,DONE,108188.0,DONE,Public strong-route control E,win,1,87809
v13r3_order_safe,5948.0,97227.0,DONE,91279.0,DONE,Public strong-route control E,win,0,87827
v13r3_order_safe,9797.0,108291.0,DONE,98494.0,DONE,Public strong-route control E,win,1,87827
v13r3_order_safe,11780.0,152049.0,DONE,140269.0,DONE,Public strong-route control E,win,0,87851
v13r3_order_safe,12021.0,152050.0,DONE,140029.0,DONE,Public strong-route control E,win,1,87851
v13r3_order_safe,8568.0,149708.0,DONE,141140.0,DONE,Public strong-route control F,win,0,87703
v13r3_order_safe,8568.0,149708.0,DONE,141140.0,DONE,Public strong-route control F,win,1,87703
v13r3_order_safe,13934.0,131018.0,DONE,117084.0,DONE,Public strong-route control F,win,0,87721
v13r3_order_safe,13236.0,143248.0,DONE,130012.0,DONE,Public strong-route control F,win,1,87721
v13r3_order_safe,6524.0,124844.0,DONE,118320.0,DONE,Public strong-route control F,win,0,87739
v13r3_order_safe,6719.0,125101.0,DONE,118382.0,DONE,Public strong-route control F,win,1,87739
v13r3_order_safe,4697.0,79829.0,DONE,75132.0,DONE,Public strong-route control F,win,0,87763
v13r3_order_safe,4187.0,79277.0,DONE,75090.0,DONE,Public strong-route control F,win,1,87763
v13r3_order_safe,4711.0,95108.0,DONE,90397.0,DONE,Public strong-route control F,win,0,87781
v13r3_order_safe,4430.0,95060.0,DONE,90630.0,DONE,Public strong-route control F,win,1,87781
v13r3_order_safe,7233.0,117319.0,DONE,110086.0,DONE,Public strong-route control F,win,0,87809
v13r3_order_safe,7233.0,117319.0,DONE,110086.0,DONE,Public strong-route control F,win,1,87809
v13r3_order_safe,3837.0,97341.0,DONE,93504.0,DONE,Public strong-route control F,win,0,87827
v13r3_order_safe,6383.0,105561.0,DONE,99178.0,DONE,Public strong-route control F,win,1,87827
v13r3_order_safe,9695.0,152128.0,DONE,142433.0,DONE,Public strong-route control F,win,0,87851
v13r3_order_safe,9830.0,152129.0,DONE,142299.0,DONE,Public strong-route control F,win,1,87851
"""))
v21_games = pd.read_csv(StringIO(r"""candidate,margin,my_reward,my_status,opp_reward,opp_status,opponent,result,seat,seed
v13r3_order_safe,4620.0,110062.0,DONE,105442.0,DONE,Exact public V21.1 artifact,win,0,93001
v13r3_order_safe,2058.0,107829.0,DONE,105771.0,DONE,Exact public V21.1 artifact,win,1,93001
v13r3_order_safe,406.0,120536.0,DONE,120130.0,DONE,Exact public V21.1 artifact,win,0,93019
v13r3_order_safe,406.0,120536.0,DONE,120130.0,DONE,Exact public V21.1 artifact,win,1,93019
v13r3_order_safe,2541.0,126920.0,DONE,124379.0,DONE,Exact public V21.1 artifact,win,0,93037
v13r3_order_safe,2541.0,126920.0,DONE,124379.0,DONE,Exact public V21.1 artifact,win,1,93037
v13r3_order_safe,3010.0,108400.0,DONE,105390.0,DONE,Exact public V21.1 artifact,win,0,93055
v13r3_order_safe,3010.0,108400.0,DONE,105390.0,DONE,Exact public V21.1 artifact,win,1,93055
v13r3_order_safe,2478.0,130567.0,DONE,128089.0,DONE,Exact public V21.1 artifact,win,0,93073
v13r3_order_safe,3388.0,130845.0,DONE,127457.0,DONE,Exact public V21.1 artifact,win,1,93073
v13r3_order_safe,5040.0,103182.0,DONE,98142.0,DONE,Exact public V21.1 artifact,win,0,93091
v13r3_order_safe,4938.0,103080.0,DONE,98142.0,DONE,Exact public V21.1 artifact,win,1,93091
v13r3_order_safe,4510.0,129291.0,DONE,124781.0,DONE,Exact public V21.1 artifact,win,0,93109
v13r3_order_safe,4643.0,129393.0,DONE,124750.0,DONE,Exact public V21.1 artifact,win,1,93109
v13r3_order_safe,618.0,125489.0,DONE,124871.0,DONE,Exact public V21.1 artifact,win,0,93127
v13r3_order_safe,618.0,125489.0,DONE,124871.0,DONE,Exact public V21.1 artifact,win,1,93127
v13r3_order_safe,1921.0,123983.0,DONE,122062.0,DONE,Exact public V21.1 artifact,win,0,93145
v13r3_order_safe,1921.0,123983.0,DONE,122062.0,DONE,Exact public V21.1 artifact,win,1,93145
v13r3_order_safe,2380.0,130670.0,DONE,128290.0,DONE,Exact public V21.1 artifact,win,0,93163
v13r3_order_safe,2380.0,130670.0,DONE,128290.0,DONE,Exact public V21.1 artifact,win,1,93163
v13r3_order_safe,1593.0,155008.0,DONE,153415.0,DONE,Exact public V21.1 artifact,win,0,93181
v13r3_order_safe,1593.0,155008.0,DONE,153415.0,DONE,Exact public V21.1 artifact,win,1,93181
v13r3_order_safe,4324.0,112136.0,DONE,107812.0,DONE,Exact public V21.1 artifact,win,0,93199
v13r3_order_safe,4324.0,112136.0,DONE,107812.0,DONE,Exact public V21.1 artifact,win,1,93199
v13r3_order_safe,954.0,85707.0,DONE,84753.0,DONE,Exact public V21.1 artifact,win,0,93217
v13r3_order_safe,954.0,85707.0,DONE,84753.0,DONE,Exact public V21.1 artifact,win,1,93217
v13r3_order_safe,2649.0,120217.0,DONE,117568.0,DONE,Exact public V21.1 artifact,win,0,93235
v13r3_order_safe,2649.0,120217.0,DONE,117568.0,DONE,Exact public V21.1 artifact,win,1,93235
v13r3_order_safe,595.0,123922.0,DONE,123327.0,DONE,Exact public V21.1 artifact,win,0,93253
v13r3_order_safe,-176.0,106642.0,DONE,106818.0,DONE,Exact public V21.1 artifact,loss,1,93253
v13r3_order_safe,416.0,132707.0,DONE,132291.0,DONE,Exact public V21.1 artifact,win,0,93271
v13r3_order_safe,416.0,132707.0,DONE,132291.0,DONE,Exact public V21.1 artifact,win,1,93271
"""))
shift_windows = pd.DataFrame(json.loads(r"""[{"step":167,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":12.0,"support":6,"next_base_quantity":12,"static_shift_cap":12},{"step":213,"item":"MILK","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":215,"item":"MILK","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":235,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":4.0,"support":6,"next_base_quantity":4,"static_shift_cap":4},{"step":258,"item":"MELON","sell_probability":1.0,"median_requested_quantity":12.0,"support":6,"next_base_quantity":12,"static_shift_cap":12},{"step":258,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":4.0,"support":6,"next_base_quantity":4,"static_shift_cap":4},{"step":260,"item":"MELON","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":260,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":261,"item":"MELON","sell_probability":1.0,"median_requested_quantity":12.0,"support":6,"next_base_quantity":12,"static_shift_cap":12},{"step":263,"item":"MELON","sell_probability":1.0,"median_requested_quantity":30.0,"support":6,"next_base_quantity":30,"static_shift_cap":30},{"step":281,"item":"MELON","sell_probability":0.8333333333333334,"median_requested_quantity":6.0,"support":5,"next_base_quantity":6,"static_shift_cap":6},{"step":283,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":287,"item":"MELON","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":287,"item":"MILK","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":308,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":310,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":310,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":8.0,"support":6,"next_base_quantity":8,"static_shift_cap":8},{"step":335,"item":"MILK","sell_probability":1.0,"median_requested_quantity":9.0,"support":6,"next_base_quantity":9,"static_shift_cap":9},{"step":335,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":356,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":375,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":3.0,"support":4,"next_base_quantity":3,"static_shift_cap":3},{"step":378,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":3.0,"support":4,"next_base_quantity":3,"static_shift_cap":3},{"step":382,"item":"WOOL","sell_probability":0.5,"median_requested_quantity":4.0,"support":3,"next_base_quantity":4,"static_shift_cap":4},{"step":383,"item":"MILK","sell_probability":1.0,"median_requested_quantity":12.0,"support":6,"next_base_quantity":12,"static_shift_cap":12},{"step":383,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":388,"item":"MILK","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":404,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":404,"item":"WOOL","sell_probability":0.5,"median_requested_quantity":4.0,"support":3,"next_base_quantity":4,"static_shift_cap":4},{"step":406,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":407,"item":"WOOL","sell_probability":0.6666666666666666,"median_requested_quantity":4.0,"support":4,"next_base_quantity":4,"static_shift_cap":4},{"step":425,"item":"MILK","sell_probability":0.5,"median_requested_quantity":3.0,"support":3,"next_base_quantity":3,"static_shift_cap":3},{"step":427,"item":"STRAWBERRY","sell_probability":0.6666666666666666,"median_requested_quantity":7.0,"support":4,"next_base_quantity":8,"static_shift_cap":8},{"step":428,"item":"MILK","sell_probability":0.5,"median_requested_quantity":6.0,"support":3,"next_base_quantity":6,"static_shift_cap":6},{"step":431,"item":"STRAWBERRY","sell_probability":0.8333333333333334,"median_requested_quantity":6.0,"support":5,"next_base_quantity":6,"static_shift_cap":6},{"step":431,"item":"MILK","sell_probability":1.0,"median_requested_quantity":12.0,"support":6,"next_base_quantity":9,"static_shift_cap":9},{"step":431,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":450,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":452,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":453,"item":"STRAWBERRY","sell_probability":0.5,"median_requested_quantity":4.0,"support":3,"next_base_quantity":4,"static_shift_cap":4},{"step":454,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":455,"item":"STRAWBERRY","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":455,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":460,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":6.0,"support":5,"next_base_quantity":6,"static_shift_cap":6},{"step":472,"item":"STRAWBERRY","sell_probability":0.6666666666666666,"median_requested_quantity":6.0,"support":4,"next_base_quantity":6,"static_shift_cap":6},{"step":473,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":3.0,"support":4,"next_base_quantity":3,"static_shift_cap":3},{"step":473,"item":"WOOL","sell_probability":0.5,"median_requested_quantity":4.0,"support":3,"next_base_quantity":4,"static_shift_cap":4},{"step":475,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":3.0,"support":4,"next_base_quantity":3,"static_shift_cap":3},{"step":478,"item":"STRAWBERRY","sell_probability":0.6666666666666666,"median_requested_quantity":6.0,"support":4,"next_base_quantity":6,"static_shift_cap":6},{"step":479,"item":"STRAWBERRY","sell_probability":1.0,"median_requested_quantity":16.0,"support":6,"next_base_quantity":16,"static_shift_cap":16},{"step":479,"item":"MILK","sell_probability":1.0,"median_requested_quantity":12.0,"support":6,"next_base_quantity":12,"static_shift_cap":12},{"step":479,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":503,"item":"STRAWBERRY","sell_probability":0.6666666666666666,"median_requested_quantity":7.0,"support":4,"next_base_quantity":8,"static_shift_cap":8},{"step":503,"item":"MILK","sell_probability":1.0,"median_requested_quantity":4.5,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":520,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":522,"item":"STRAWBERRY","sell_probability":1.0,"median_requested_quantity":8.0,"support":6,"next_base_quantity":8,"static_shift_cap":8},{"step":522,"item":"MELON","sell_probability":0.8333333333333334,"median_requested_quantity":6.0,"support":5,"next_base_quantity":6,"static_shift_cap":6},{"step":522,"item":"MILK","sell_probability":1.0,"median_requested_quantity":6.0,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":522,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":523,"item":"STRAWBERRY","sell_probability":0.8333333333333334,"median_requested_quantity":31.0,"support":5,"next_base_quantity":31,"static_shift_cap":30},{"step":524,"item":"MELON","sell_probability":0.8333333333333334,"median_requested_quantity":24.0,"support":5,"next_base_quantity":24,"static_shift_cap":24},{"step":524,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":526,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":3.0,"support":4,"next_base_quantity":3,"static_shift_cap":3},{"step":527,"item":"STRAWBERRY","sell_probability":1.0,"median_requested_quantity":4.0,"support":6,"next_base_quantity":4,"static_shift_cap":4},{"step":527,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":527,"item":"WOOL","sell_probability":0.6666666666666666,"median_requested_quantity":4.0,"support":4,"next_base_quantity":4,"static_shift_cap":4},{"step":551,"item":"STRAWBERRY","sell_probability":1.0,"median_requested_quantity":20.0,"support":6,"next_base_quantity":20,"static_shift_cap":20},{"step":551,"item":"MELON","sell_probability":1.0,"median_requested_quantity":34.5,"support":6,"next_base_quantity":33,"static_shift_cap":30},{"step":551,"item":"MILK","sell_probability":1.0,"median_requested_quantity":7.5,"support":6,"next_base_quantity":9,"static_shift_cap":9},{"step":551,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":8.0,"support":5,"next_base_quantity":8,"static_shift_cap":8},{"step":571,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":572,"item":"STRAWBERRY","sell_probability":0.6666666666666666,"median_requested_quantity":19.0,"support":4,"next_base_quantity":19,"static_shift_cap":19},{"step":572,"item":"MILK","sell_probability":0.5,"median_requested_quantity":3.0,"support":3,"next_base_quantity":3,"static_shift_cap":3},{"step":572,"item":"WOOL","sell_probability":0.5,"median_requested_quantity":4.0,"support":3,"next_base_quantity":4,"static_shift_cap":4},{"step":574,"item":"WOOL","sell_probability":0.5,"median_requested_quantity":4.0,"support":3,"next_base_quantity":4,"static_shift_cap":4},{"step":575,"item":"STRAWBERRY","sell_probability":1.0,"median_requested_quantity":43.5,"support":6,"next_base_quantity":47,"static_shift_cap":30},{"step":575,"item":"MILK","sell_probability":1.0,"median_requested_quantity":9.0,"support":6,"next_base_quantity":9,"static_shift_cap":9},{"step":596,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":598,"item":"MILK","sell_probability":1.0,"median_requested_quantity":4.5,"support":6,"next_base_quantity":6,"static_shift_cap":6},{"step":599,"item":"STRAWBERRY","sell_probability":1.0,"median_requested_quantity":14.5,"support":6,"next_base_quantity":14,"static_shift_cap":14},{"step":599,"item":"MILK","sell_probability":0.8333333333333334,"median_requested_quantity":6.0,"support":5,"next_base_quantity":6,"static_shift_cap":6},{"step":599,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":8.0,"support":6,"next_base_quantity":8,"static_shift_cap":8},{"step":619,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":7.5,"support":4,"next_base_quantity":9,"static_shift_cap":9},{"step":620,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":6.0,"support":4,"next_base_quantity":6,"static_shift_cap":6},{"step":621,"item":"MILK","sell_probability":1.0,"median_requested_quantity":3.0,"support":6,"next_base_quantity":3,"static_shift_cap":3},{"step":622,"item":"STRAWBERRY","sell_probability":0.6666666666666666,"median_requested_quantity":14.0,"support":4,"next_base_quantity":14,"static_shift_cap":14},{"step":623,"item":"STRAWBERRY","sell_probability":0.8333333333333334,"median_requested_quantity":38.0,"support":5,"next_base_quantity":42,"static_shift_cap":30},{"step":623,"item":"WOOL","sell_probability":0.8333333333333334,"median_requested_quantity":4.0,"support":5,"next_base_quantity":4,"static_shift_cap":4},{"step":645,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":3.0,"support":4,"next_base_quantity":3,"static_shift_cap":3},{"step":647,"item":"STRAWBERRY","sell_probability":0.6666666666666666,"median_requested_quantity":7.5,"support":4,"next_base_quantity":9,"static_shift_cap":9},{"step":647,"item":"MILK","sell_probability":0.6666666666666666,"median_requested_quantity":3.0,"support":4,"next_base_quantity":3,"static_shift_cap":3},{"step":647,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":8.0,"support":6,"next_base_quantity":8,"static_shift_cap":8},{"step":667,"item":"STRAWBERRY","sell_probability":0.6666666666666666,"median_requested_quantity":4.0,"support":4,"next_base_quantity":4,"static_shift_cap":4},{"step":669,"item":"MILK","sell_probability":0.8333333333333334,"median_requested_quantity":3.0,"support":5,"next_base_quantity":3,"static_shift_cap":3},{"step":670,"item":"MILK","sell_probability":0.5,"median_requested_quantity":3.0,"support":3,"next_base_quantity":3,"static_shift_cap":3},{"step":670,"item":"WOOL","sell_probability":0.5,"median_requested_quantity":4.0,"support":3,"next_base_quantity":4,"static_shift_cap":4},{"step":671,"item":"STRAWBERRY","sell_probability":1.0,"median_requested_quantity":32.0,"support":6,"next_base_quantity":31,"static_shift_cap":30},{"step":671,"item":"MILK","sell_probability":1.0,"median_requested_quantity":12.0,"support":6,"next_base_quantity":12,"static_shift_cap":12},{"step":671,"item":"WOOL","sell_probability":1.0,"median_requested_quantity":8.0,"support":6,"next_base_quantity":8,"static_shift_cap":8}]"""))

for frame in (gold_games, public_games, v21_games):
    for column in ["seed", "seat"]:
        frame[column] = frame[column].astype(int)
    for column in ["margin", "my_reward", "opp_reward"]:
        frame[column] = frame[column].astype(float)

assert len(gold_games) == 96
assert len(public_games) == 96
assert len(v21_games) == 32 and v21_games["seed"].nunique() == 16
assert set(v21_games.groupby("seed")["seat"].apply(frozenset)) == {frozenset({0, 1})}
assert v21_games[["my_status", "opp_status"]].eq("DONE").all().all()
assert len(shift_windows) == 98 and shift_windows["step"].nunique() == 64

print(
    "Validated frozen evidence: 224 local games; "
    "the V21.1 panel contains 16 seeds x 2 seats; "
    "98 static premium-shift candidates span 64 steps."
)
```

**output:**

```text
Validated frozen evidence: 224 local games; the V21.1 panel contains 16 seeds x 2 seats; 98 static premium-shift candidates span 64 steps.
```

## cell [2] — markdown

## 1. The top-meta problem: same production, different market outcome

Kaggriculture has a shared market. A `SELL` increases market inventory, which can lower the price received by later sales. When two strong agents have converged on similar crop, animal, labor, and land schedules, production volume is no longer the only differentiator: market timing and order position become part of the policy.

Suppose both agents plan to sell the same premium item at turn `t+1`. V13-R3 applies a **conservative one-turn shift**:

| Policy | Turn `t` | Turn `t+1` | Two-turn quantity |
|:---|:---:|:---:|:---:|
| Base schedule | — | `SELL item q` | `q` |
| V13-R3 | `SELL item s` | `SELL item (q - s)` | `s + (q - s) = q` |

The table states the invariant; the figure below shows the timing change visually. The normal two-turn sale quantity is conserved, so the intervention changes timing rather than the underlying production plan.

## cell [3] — code

```python
# Mechanism diagram. The quantities are illustrative; the invariant is exact.
from matplotlib.patches import FancyArrowPatch

planned_next = 30
shifted_now = 12
repaid_next = planned_next - shifted_now

fig, ax = plt.subplots(figsize=(10.5, 3.5))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")
ax.set_xlim(-0.28, 1.22)
ax.set_ylim(-0.28, 1.55)
ax.axis("off")

# Quiet time anchors.
for x, label in [(0, "turn t"), (1, "turn t+1")]:
    ax.plot([x, x], [0.03, 1.12], color=LIGHT, lw=1.2, zorder=0)
    ax.text(x, -0.08, label, ha="center", va="top", color=SLATE, fontsize=10)

ax.text(-0.22, 1.04, "Base schedule", ha="left", va="center", color=SLATE, weight="bold")
ax.text(-0.22, 0.27, "V13-R3", ha="left", va="center", color=DARK, weight="bold")

card = dict(boxstyle="round,pad=0.65", edgecolor="none")
ax.text(
    1, 1.04, f"SELL q = {planned_next}", ha="center", va="center", color="white", weight="bold",
    bbox={**card, "facecolor": SLATE}, zorder=3,
)
ax.text(
    0, 0.27, f"SELL s = {shifted_now}", ha="center", va="center", color="white", weight="bold",
    bbox={**card, "facecolor": ORANGE}, zorder=3,
)
ax.text(
    1, 0.27, f"SELL q - s = {repaid_next}", ha="center", va="center", color="white", weight="bold",
    bbox={**card, "facecolor": TEAL}, zorder=3,
)

ax.add_patch(FancyArrowPatch(
    (0.94, 0.91), (0.12, 0.39),
    connectionstyle="arc3,rad=0.18", arrowstyle="-|>", mutation_scale=13,
    lw=2, color=ORANGE,
))
ax.text(0.50, 0.76, "12 units shift earlier", ha="center", va="center",
        color=ORANGE, weight="bold", fontsize=10)
ax.add_patch(FancyArrowPatch(
    (1.00, 0.87), (1.00, 0.43),
    arrowstyle="-|>", mutation_scale=12, lw=1.8, color=TEAL,
))
ax.text(1.06, 0.66, "18 remain", ha="left", va="center", color=TEAL, weight="bold", fontsize=9)

ax.text(
    0.5, 1.40, "Planned quantity is split across two turns",
    ha="center", va="center", color=DARK, fontsize=12, weight="bold",
)
ax.text(
    0.5, 1.24, f"Quantity conserved: {planned_next} = {shifted_now} + {repaid_next}",
    ha="center", va="center", color=SLATE, fontsize=10,
)
plt.tight_layout()
plt.show()
```

**output:**

*[image omitted — see the notebook]*

## cell [4] — markdown

## 2. Agent architecture and activation gates

The premium controller is an overlay on a complete playable agent, not a standalone market script.

| Layer | Runtime role |
|---|---|
| 719-turn production schedule | Executes the full labor, land, crop, animal, and base-market plan |
| Hand alignment | Pads or truncates `hands` actions to match the current public hand count |
| Actor-local `WEED` recovery | Uses `DIG`, retry, and a bounded two-step catch-up when random weeds block `PLANT` or `BUILD_PASTURE` |
| Near-mirror gate | Compares public crop, animal, structure, hand, and `unlocked_quadrants` counts; clone distance must be at most 6 |
| Premium shift | Covers `STRAWBERRY`, `MELON`, `MILK`, and `WOOL` only, during `120 <= step < 680` |
| Quantity bounds | Caps a shifted item at 30 and also respects the next base `SELL`, projected own shed, and replay-prior median |
| Repayment | Deducts the shifted quantity from the next scheduled `SELL` of the same item |
| Safe market and liquidation | Clamps every `SELL` to projected own inventory, keeps at most 10 market orders, and liquidates on the final turn |

The replay-derived prior uses one representative public replay from each of six exact top-route submissions, preventing teams with more available replays from receiving extra weight. A plotted point below is only a **static candidate**. Runtime activation still requires the near-mirror gate, sufficient own inventory, a future base sale, and available market-order capacity.

## cell [5] — code

```python
item_order = ["WOOL", "MILK", "MELON", "STRAWBERRY"]
item_y = {item: index for index, item in enumerate(item_order)}

fig, ax = plt.subplots(figsize=(11, 4.6))
scatter = ax.scatter(
    shift_windows["step"],
    shift_windows["item"].map(item_y),
    s=25 + shift_windows["static_shift_cap"] * 6,
    c=shift_windows["sell_probability"],
    cmap="viridis",
    vmin=0.5,
    vmax=1.0,
    alpha=0.82,
    edgecolor="white",
    linewidth=0.4,
)
ax.set_yticks(range(len(item_order)), item_order)
ax.set_xlim(120, 680)
ax.set_xlabel("step used for one-turn preemption")
ax.set_title("Static premium-shift candidate windows", loc="left", color=DARK, weight="bold", pad=24)
ax.text(
    0,
    1.02,
    "Marker size = static quantity cap; color = sale support across six representative replays",
    transform=ax.transAxes,
    color=SLATE,
)
ax.grid(axis="x", alpha=0.14)
ax.spines[["top", "right", "left"]].set_visible(False)
colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
colorbar.set_label("sell probability")
plt.tight_layout()
plt.show()

window_summary = (
    shift_windows.groupby("item")
    .agg(
        candidate_rows=("step", "size"),
        distinct_steps=("step", "nunique"),
        first_step=("step", "min"),
        last_step=("step", "max"),
    )
    .reindex(item_order)
    .reset_index()
)
window_summary.columns = [
    "Item", "Candidate windows", "Distinct steps", "First step", "Last step"
]
from IPython.display import Markdown

table_lines = [
    "**Static premium-shift coverage by item**",
    "",
    "| Item | Candidate windows | Distinct steps | First step | Last step |",
    "|:---|---:|---:|---:|---:|",
]
for row in window_summary.itertuples(index=False):
    table_lines.append(
        f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |"
    )
display(Markdown("\n".join(table_lines)))
```

**output:**

*[image omitted — see the notebook]*

**output:**

**Static premium-shift coverage by item**

| Item | Candidate windows | Distinct steps | First step | Last step |
|:---|---:|---:|---:|---:|
| WOOL | 28 | 28 | 167 | 671 |
| MILK | 41 | 41 | 213 | 671 |
| MELON | 9 | 9 | 258 | 551 |
| STRAWBERRY | 20 | 20 | 427 | 671 |

## cell [6] — markdown

## 3. Why R3 is order-safe

An earlier controller prototype inserted a newly shifted sale at the front of the current market queue:

```python
market.insert(0, ["SELL", item, target])
```

That is unnecessarily aggressive. The goal is to move ahead of the opponent's likely **next-turn** sale, not ahead of this agent's existing same-turn orders. Front insertion can delay a higher-value base sale—especially `STRAWBERRY`—and reverse the intended benefit.

R3 instead uses:

```python
market.append(["SELL", item, target])
```

If the current market queue already contains a `SELL` for the same item, the controller merges quantities at that existing position. This preserves the base schedule's same-turn priority while still preempting the next-turn hazard.

## cell [7] — code

```python
# Queue comparison: the same three orders are shown in two execution sequences.
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

base_market = [
    ["SELL", "STRAWBERRY", 24],
    ["HIRE"],
]
shifted_order = ["SELL", "MILK", 6]
queues = {
    "Front insertion": [shifted_order] + base_market,
    "R3 append": base_market + [shifted_order],
}

def order_label(order):
    if order[0] == "HIRE":
        return "HIRE"
    return f"SELL {order[1]} {order[2]}"

def order_color(order):
    if order[0] == "HIRE":
        return SLATE
    return TEAL if order[1] == "STRAWBERRY" else ORANGE

fig, ax = plt.subplots(figsize=(11, 3.8))
fig.patch.set_facecolor("white")
ax.set_facecolor("white")
ax.set_xlim(-0.12, 2.92)
ax.set_ylim(-0.22, 1.68)
ax.axis("off")

row_specs = [
    (0.96, "Prototype — front insertion", queues["Front insertion"]),
    (0.18, "V13-R3 — append", queues["R3 append"]),
]
x_positions = [0.08, 1.08, 2.08]
box_width, box_height = 0.72, 0.30

for y, row_title, queue in row_specs:
    ax.text(0.08, y + 0.25, row_title, ha="left", va="center", color=DARK, weight="bold")
    for index, (x, order) in enumerate(zip(x_positions, queue), start=1):
        color = order_color(order)
        ax.add_patch(FancyBboxPatch(
            (x, y - box_height / 2), box_width, box_height,
            boxstyle="round,pad=0.035,rounding_size=0.04",
            linewidth=0, facecolor=color,
        ))
        ax.text(x + 0.10, y, str(index), ha="center", va="center", color="white",
                weight="bold", fontsize=9,
                bbox=dict(boxstyle="circle,pad=0.20", facecolor=DARK, edgecolor="none"))
        ax.text(x + 0.47, y, order_label(order), ha="center", va="center",
                color="white", weight="bold", fontsize=9)
        if index < 3:
            ax.add_patch(FancyArrowPatch(
                (x + box_width + 0.05, y), (x_positions[index] - 0.05, y),
                arrowstyle="-|>", mutation_scale=11, lw=1.4, color=SLATE,
            ))

ax.text(-0.08, 1.58, "Same three market orders, two execution queues",
        ha="left", va="center", color=DARK, fontsize=13, weight="bold")
ax.text(-0.08, 1.39, "Each row contains the same orders. Execution runs left to right.",
        ha="left", va="center", color=SLATE, fontsize=10)
plt.tight_layout()
plt.show()

assert queues["R3 append"][0] == ["SELL", "STRAWBERRY", 24]
```

**output:**

*[image omitted — see the notebook]*

## cell [8] — markdown

## 4. Paired-seat evaluation protocol

All numbers below come from frozen local cross-play under `kaggle-environments==1.32.4`. Every seed is played twice with seats exchanged:

```text
paired margin(seed) = margin as seat 0 + margin as seat 1
```

The main frontier panel uses 16 seeds that were not used to tune V13, for 32 games against the exact public V21.1 artifact. Both artifacts were hash-locked before testing:

- V13-R3 SHA-256: `6f52902081fed08bb5da08d575b796437e645c5320662b448b81eb079f185cfb`
- exact public V21.1 SHA-256: `d9dc24ce5429ec628ead0621a160bee90725350683d7dfcc4686fcaf511f3aab`

Two separate regression panels cover six replay-derived top-route proxies and six public strong-route controls. Because the opponent sets answer different questions, the notebook reports them separately instead of combining them into one headline win rate.

## cell [9] — code

```python
def summarize_panel(label, frame):
    paired = frame.groupby(["opponent", "seed"], as_index=False)["margin"].sum()
    return {
        "panel": label,
        "games": len(frame),
        "wins": int((frame["margin"] > 0).sum()),
        "losses": int((frame["margin"] < 0).sum()),
        "win_rate": float((frame["margin"] > 0).mean()),
        "mean_margin": float(frame["margin"].mean()),
        "worst_game": float(frame["margin"].min()),
        "paired": len(paired),
        "paired_positive": int((paired["margin"] > 0).sum()),
        "paired_negative": int((paired["margin"] < 0).sum()),
        "paired_positive_rate": float((paired["margin"] > 0).mean()),
        "worst_paired": float(paired["margin"].min()),
    }

panel_summary = pd.DataFrame([
    summarize_panel("Top-route replay proxies", gold_games),
    summarize_panel("Public strong-route controls", public_games),
    summarize_panel("Exact public V21.1", v21_games),
])

summary_view = panel_summary.copy()
summary_view["record"] = summary_view["wins"].astype(str) + "-" + summary_view["losses"].astype(str)
summary_view["win_rate"] = summary_view["win_rate"].map(lambda value: f"{value:.1%}")
summary_view["paired_record"] = (
    summary_view["paired_positive"].astype(str)
    + "/"
    + summary_view["paired"].astype(str)
    + " positive"
)
summary_view["mean_margin"] = summary_view["mean_margin"].map(lambda value: f"{value:+,.1f}")
summary_view["worst_game"] = summary_view["worst_game"].map(lambda value: f"{value:+,.0f}")
summary_view["worst_paired"] = summary_view["worst_paired"].map(lambda value: f"{value:+,.0f}")
display(summary_view[[
    "panel", "games", "record", "win_rate", "paired_record",
    "mean_margin", "worst_game", "worst_paired"
]])

exact = panel_summary.loc[panel_summary["panel"].eq("Exact public V21.1")].iloc[0]
top_route = panel_summary.loc[panel_summary["panel"].eq("Top-route replay proxies")].iloc[0]
public_controls = panel_summary.loc[
    panel_summary["panel"].eq("Public strong-route controls")
].iloc[0]
assert (exact["wins"], exact["losses"]) == (31, 1)
assert (exact["paired_positive"], exact["paired_negative"]) == (16, 0)
assert exact["worst_game"] == -176 and exact["worst_paired"] == 419
assert (top_route["wins"], top_route["losses"]) == (91, 5)
assert (top_route["paired_positive"], top_route["paired_negative"]) == (46, 2)
assert (public_controls["wins"], public_controls["losses"]) == (96, 0)
assert (public_controls["paired_positive"], public_controls["paired_negative"]) == (48, 0)
```

**output:**

```text
panel | games | record | win_rate | paired_record | mean_margin | worst_game | worst_paired
0 | Top-route replay proxies | 96 | 91-5 | 94.8% | 46/48 positive | +4,396.1 | -995 | -897
1 | Public strong-route controls | 96 | 96-0 | 100.0% | 48/48 positive | +9,994.5 | +3,837 | +8,884
2 | Exact public V21.1 | 32 | 31-1 | 96.9% | 16/16 positive | +2,303.7 | -176 | +419
```

## cell [10] — code

```python
v21_paired = (
    v21_games.pivot(index="seed", columns="seat", values="margin")
    .rename(columns={0: "seat 0", 1: "seat 1"})
)
v21_paired["paired total"] = v21_paired.sum(axis=1)
v21_paired = v21_paired.sort_index()

fig, (ax_left, ax_right) = plt.subplots(
    1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.45, 1]}
)

x = range(len(v21_paired))
ax_left.plot(x, v21_paired["seat 0"], marker="o", color=TEAL, label="V13-R3 as seat 0")
ax_left.plot(x, v21_paired["seat 1"], marker="s", color=ORANGE, label="V13-R3 as seat 1")
ax_left.axhline(0, color=SLATE, linewidth=1)
ax_left.set_xticks(list(x), [str(seed) for seed in v21_paired.index], rotation=55, ha="right", fontsize=8)
ax_left.set_ylabel("V13-R3 final margin (coins)")
ax_left.set_title("Per-seat margins: 31 wins / 1 loss", loc="left", color=DARK, weight="bold")
ax_left.legend(frameon=False)
ax_left.grid(axis="y", alpha=0.14)
ax_left.spines[["top", "right"]].set_visible(False)

colors = [TEAL if value > 0 else ORANGE for value in v21_paired["paired total"]]
ax_right.barh([str(seed) for seed in v21_paired.index], v21_paired["paired total"], color=colors)
ax_right.axvline(0, color=SLATE, linewidth=1)
ax_right.set_xlabel("seat 0 + seat 1 margin")
ax_right.set_title("Paired seeds: 16 / 16 positive", loc="left", color=DARK, weight="bold")
ax_right.invert_yaxis()
ax_right.grid(axis="x", alpha=0.14)
ax_right.spines[["top", "right", "left"]].set_visible(False)

plt.tight_layout()
plt.show()

display(v21_paired.apply(lambda column: column.map(lambda value: f"{value:+,.0f}")))
```

**output:**

*[image omitted — see the notebook]*

**output:**

```text
seat | seat 0 | seat 1 | paired total
seed
93001 | +4,620 | +2,058 | +6,678
93019 | +406 | +406 | +812
93037 | +2,541 | +2,541 | +5,082
93055 | +3,010 | +3,010 | +6,020
93073 | +2,478 | +3,388 | +5,866
93091 | +5,040 | +4,938 | +9,978
93109 | +4,510 | +4,643 | +9,153
93127 | +618 | +618 | +1,236
93145 | +1,921 | +1,921 | +3,842
93163 | +2,380 | +2,380 | +4,760
93181 | +1,593 | +1,593 | +3,186
93199 | +4,324 | +4,324 | +8,648
93217 | +954 | +954 | +1,908
93235 | +2,649 | +2,649 | +5,298
93253 | +595 | -176 | +419
93271 | +416 | +416 | +832
```

## cell [11] — code

```python
chart = panel_summary.set_index("panel")
fig, axes = plt.subplots(1, 2, figsize=(12.5, 3.9))

axes[0].barh(chart.index, chart["win_rate"], color=[TEAL_LIGHT, TEAL, "#115E59"])
axes[0].axvline(0.5, color=SLATE, linestyle="--", linewidth=1)
axes[0].set_xlim(0, 1.04)
axes[0].set_xlabel("per-game win rate")
axes[0].set_title("Frozen regression panels", loc="left", color=DARK, weight="bold")
for index, value in enumerate(chart["win_rate"]):
    axes[0].text(value + 0.012, index, f"{value:.1%}", va="center", color=DARK)

axes[1].barh(chart.index, chart["paired_positive_rate"], color=[TEAL_LIGHT, TEAL, "#115E59"])
axes[1].axvline(0.5, color=SLATE, linestyle="--", linewidth=1)
axes[1].set_xlim(0, 1.04)
axes[1].set_xlabel("paired-seed positive rate")
axes[1].set_title("Seat-swapped aggregate", loc="left", color=DARK, weight="bold")
for index, value in enumerate(chart["paired_positive_rate"]):
    axes[1].text(value + 0.012, index, f"{value:.1%}", va="center", color=DARK)

for ax in axes:
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.14)
    ax.spines[["top", "right", "left"]].set_visible(False)

plt.tight_layout()
plt.show()
```

**output:**

*[image omitted — see the notebook]*

## cell [12] — markdown

## 5. Failure audit

The exact V21.1 panel has one losing game: seed `93253`, with V13-R3 in seat 1, at `-176`. After swapping seats, V13-R3 wins by `+595`, leaving that seed's paired margin at `+419`. It is the thinnest paired advantage in the 16-seed panel.

The broader top-route proxy holdout finishes `91-5`, with `46 / 48` paired matchups positive. The two paired negatives occur against different proxy agents; the worst is `-897`. This evidence supports an advantage inside a highly converged production basin, but it does not imply an unconditional win against every variant, nor should 224 frozen local games be presented as a future leaderboard win rate.

The failure pattern also argues against simply increasing the shift size. The main lesson from the pre-R3 prototype was the opposite: even when two-turn quantity is conserved, placing a new order at the wrong position in the agent's own queue can create a self-inflicted loss. Future work should focus on order interactions, partial repayment under limited inventory, and fresh paired seeds with narrow margins.

## cell [13] — markdown

## 6. Implementation provenance and related public research

The 719-action production schedule was reconstructed from public replay observations of OceanMix episode `90343084`, source seat 0. The `SELL` hazard prior was built from one representative public replay for each of six exact top-route submissions and aggregated as `(item, sell probability, median requested quantity, support)`. The online agent never reads replay files: the exact `main.py` below uses only the Python standard library and the current observation.

V13-R3 was implemented independently. Public notebooks were used as research references and evaluation targets, not as source-code dependencies:

- [Kaito v20 — WEED Slip Recovery](https://www.kaggle.com/code/kaitofukami/159-160-vs-frontier-v20-weed-slip-recovery): public discussion of actor-local recovery and artifact validation;
- [Kaito v21.1 — Conditional Memory](https://www.kaggle.com/code/kaitofukami/177-180-fresh-top-30-v21-1-conditional-memory): the exact public comparison artifact used in the 32-game panel;
- [Findings from Zero to Top Meta](https://www.kaggle.com/code/raykkretzschmar/kaggriculture-findings-from-zero-to-top-meta): paired-seat testing and the boundary between local evidence and leaderboard behavior;
- [The Moon Counts Melons](https://www.kaggle.com/code/prvsiyan/kaggriculture-frontier-the-moon-counts-melons): market-timing analysis within converged production routes.

Exact V13-R3 artifact: **28,715 bytes**  
SHA-256: `6f52902081fed08bb5da08d575b796437e645c5320662b448b81eb079f185cfb`

## cell [14] — markdown

## 7. Full V13-R3 implementation

The following is the complete, independently implemented source used in every V13-R3 result above. It is reproduced verbatim and hash-checked again in the artifact cell that follows.

```python

"""Replay-derived clean-room Kaggriculture research candidate.

The production trace was transcribed from actions visible in one public replay.
No source code or runtime replay access is used.  The wrapper adds only hand
alignment, bounded actor-local weed repair, safe SELL clamping, and final shed
liquidation.
"""
import base64
import copy
import json
import zlib


_ACTIONS = json.loads(zlib.decompress(base64.b85decode((
    'c-rk<O>Z2@k^L_`^Pv79Mft{&+LmCBC{WZkyo1JI0NXII@E&IOw%Gq}jYw8iSG;)fA~LH*jeKj6-Bpp1QCacv;>Az@clP&Re*Nd)'
    'em(ocPiG&lKYlzroS*&Um;e6j|9t+#=a2vV<=6lE+y8$4{L|UncXzwb|J6SH@aZo<U%!9%<Mqwi`Ps*}yWNMg^R@ZM>)ZY0&mVWY'
    'H=qBwf4jTBKRbUp`}2>xo7?wi=d1PM@c-vWQonos=T9FdR~zL2>1@CIc>hJ7_qTWVZ@+wcT;$|;Q}G^taJ=x}g!piG`{vW@`%ye2'
    '#t)y~-Msnv^VRP^ebK>0it*-5jN!uL_oi~pSABE+diS_!{buH$<PMLzn_POnM0gALOXOBWcf$^TUhw--|HmqP)WyR_HtO%`J`eWx'
    '#U`%rcX!8k{NrynIhE@1+bMO9*Bux6bc5H|kIH-eQYYn&iyH1Ue8-x8xB|N;Kv&ivW<TS*baVqzd)6RgH9lQ0slLGy8q`NkZLkF0'
    ')aKU}wKiHp7iHlGb-v(8Yx8%KsI|$TbhVjVb<!4CgRc?uugSwzP!>>#uOs1sBug<LI;qHhaFo_f?wPK-$$k9c^p|}+OB@Fe`Z*id'
    '-5S1-x}Ncy9uLr_Ys`<<uO&x8zvdcGF4ga1F}v&bjp-rB>)V@~-Rt|G|G2xme|PilKaXEtl`DR{{nWlq{l$87cl%-4r|IMF=C{yo'
    'BJvo)En*Pi3AAdw-m`h)nBvQpld;=gHvuti(wfv9Lt%G$Rv?ZX=Q};U%;>D^*PEYjN7q9;U_30S((&PNG_^W}0m>){@PDmO*KlvE'
    ')X@pEO6|JrCjG}sNF0v26hW+n%&kd4SK9kt%LZY~ce-wHk}R}vHzMkE@3|8ImpgoT`1W$Q{ti~nU*t+GyqFHit$&{?D1`RU_0D~-'
    '|1Di@=HG5J{_R%vZ@Htp#nm*$vr>v;j~7$2j?94qx0v5vh?G*UYVwwC>N=_-)x7<AmbAC7Pyoc-%Gv)ax3o&MD*`o1c+ggzcyh<W'
    '5;Jcy_FAvskmxi_!S_hJiT7)X3O5~J+KCrgLLiep`3f>TJEefa=6A0XaOnP9DZQ#%&r*bMx-huZW#w9-=O;UF|1KW%g$F$A<3UdY'
    'wB9~6#c?g<L=Q-pCMTLeof?(`yy`fGxSaOvB1f2z;vglG;|x01kR=z~K`Cw#mb+OjK|cKN?e*P%sE+VP$do=h|9t5>sAdok-UG$6'
    'bK|b!4z2j3EDEH}s%H9o957?VAh`?jrOagpbxBd4kPK%^n(u$6-a7ti`UzY*5}Ks45sVO5vIJxnfnYw}Z@TGrCGhFX>;OR&dIdW9'
    '*|S<adIGE>$32U67kc1kVZb6DAsxg2awah>09<*#rtp-8)%xU`sr5VC8LvE@k$rl_TsZ66`0Wfh&uTKK=0PbqOoc>Z>Q(S?k(6L)'
    'i&A2SQG**hr{qk7A%&lKNxzg}wyYHjmehGgfo?xUD6X3mYd9E_3-&TlEk|=TWd2@$(h}NVw1@Wa*Oz@m_f7wZ{bX@^w-T3qMJyVW'
    '_fZgAP(?pXZls`&U^J3B>5K@<1&UqK895l1-NDl>JKpV0qH<!F&5}s^8M4V0ft80blNC{bbBWN!kHU%qDp;c?^j6k?v9gl1d%X5s'
    'nNo?*8)`{OU8Epl`vv7z)RGc5sff8ZauJ5Kx3@Q68syJ?rwhE8RB!9%`u&@HZ+{%8&D-~}dxN|K(JOp4tMh!kzq{W5u)Dka%h~x='
    '`~s$3?|!joxhl;ZbTl5fKBGah_uq?J@%6@&Fmn$@)8m!F|DFUH3LdlXEUj&?$=uIlg>M<A_u=C6LL4eOOl-V$4?uSddNub&$pU``'
    'Xadwo22Css8%K&h5`-D^d<C7P6ayEJE#vrP3k<0RifxQ;*vH|+yj~g<T^f9Fd22yK5;_8fT>6%PdJ|h}wT2Gj>_#SpV=0i)*T&ie'
    'G7I~9LBJfv+Kao(t<5+IS%JS!-l?$K86PAab%*Re)Mo-sl@L_{AF@cTt1$f#ccNq+k(lS*lIFec)`X!vKS>Td4MO7_XVb`Jn+Tnz'
    'M>l+#iyUJOsrS{3`0X&VX4wvYEO_#h;PGD_#G<Hkr(q4i_iU5w)j<yi(47Xc>9;D-x6IZWX0-YHU^jPKfNWiaBpV9?8N07mn!r^N'
    '<)ZunEN(<(V4ijXE^eU>=bmPWJc<-87lmGAU&cI|Wmyha;7)c5aaAC@j`fZ4OI=h7^3>*e2ar4mQRVQPh3!Pzxeh^<V9yCO(Z^ec'
    'd1BRLB<MQlxuI}SA0XabJelC$NDH5f0M1o|z}YPU{UH7j=*j-Ct)Rr&^$@nUB7sd+cxS8GA&AhF=sPQ7!T2!sob@Wl$O@uJ&n1gm'
    '+KrhkVODug3dXPNS|+^t!?m;E_I~##QSy)PZvOlmCP)OX=Cl+s1Cd&DIxY<>e|Du$ukcMNO63II(<t?2K1yAyQR=EGN`3fH18rFn'
    'gqGlRe!0|pZ^kc-1E*XpTC4!h`ig>VeLqP^xxf}Ro~m?OFzggQ#w*pf3b;yo5JUwoz>V#;k&X1LEq=UF09xBvCe{yV^pa!XN~)3G'
    'numvEQ!CySun4<_VLehT7Uz8%t?HQBV7;cm3aOzLGPi;ONIL?*a;P%#QEbeLleD9~8u#=&QdO&(3H`2=6wrA^$Z?mWe2E>3GF#GC'
    'bl$HfW|Uq+5EuSrGAvLdtJev?AOg3GlnK9mH9bSEG?VL}Hv~tlFrmb28}!EuJ#@oK=yfKBvrtG}VFcBSg}|E3WgMiS6~_i~6dn#%'
    'K<tZTl_(@^ylel$QNiV%vTpmJ5xY||1hNX<<M3L$SC+WJuT3n`o&=NIz}CegUr*#HQXudc(cb!07!8m^;44wV=xLS0&u#j#hw+WK'
    '0V@2yWS<E{qPY3YK0)%PFQgOfz7K}P553`_=nViA^$2ujQy$hnmP1X3wQqv=7#Aa1Wt%qnu|0|cJOh?XnhSZUw@OnCs{c?3pq1GN'
    'E^n;5sm7>W<EQah!lH&nERn@0N@sF<lY|Y9!%)woU=L^z*pj@5b2gfy_UwhD%3AKvgP5#7_@KmT+3cZ^w#hueVN+?kZ0QZUrB5ii'
    'S5&H8vM~9umdy*N2>Y^Bp42)Kqq)H#S%mPkyu}ax7oBrer0}%Zx(-KSZ3DdRR7c|j49){T@(Uq_bqKLQ-{JN8`59OCqGt<dk@7;}'
    '@U&;fZ!KgIsI(xo{>q93Dg_G*2HK<>!-BH(LUi+rfVQCG9k-1ISR}A6zvrwEr8~l2Yi(|bo{|mb4QjQHZX{2<iR@$8NY-GiBbaH-'
    'L2Bxw&P?MR7+l=7M|5iHvr{M9wGjJly(D@<)!K?PNew@LMV{#SxN5m>J^oMz?i2pczIhRl(u`5#Dy)|3aG{1z0RB`_61qWCsC9V2'
    '`ze%8LA*xScwX#&WzhzX%5{iNUp?p~qzv36f!V>cu0vfi46HBR<-a^s;q%dhA&jRF0S*-4taT?esA9eX$K6&R1_?f)L#>E@<78RJ'
    'AZ+hKXr%&SFh#zMYl^b61WewrW?p59Hl_~fL9fGIkStR3Q+X}mHmKrDA%`LwwLNCz^2bcr1)orc3_8)Cf_QYO+(Z_(F>D+wP&yk('
    '_X%a=&fC7!&anVU2&DRRw%S?n6fa!rL);6qECqs_H23;!Rxi2`C8XO-E{e%piySJE&aJkUrg<r&)f=K@lU}13sLfk$)2U`8?0XXw'
    'M14?1pJXiC919RCK$6y#or%(sE}25-oe8~1MzPQWrpfG_wW9#5(voYsDDw~Gys=pG4XM;iJ*Bi)aPeAy6Pebc=e%kY?g?(C6Sd)1'
    '^2o<h9mzRB(1^f9mQWhwBN)ygBVvx=fj?iBT@1nsG+rk&Ld$w{V7q9(Y_#=a8@tiHH!w<^Ko-uNOT~?fPzinO**oRV!NXFe5FiW%'
    'WDgY1Y70!rgFDn5WVZK7RtDuT2*6Dy;7#`J6LrmSK`>bz4-Kn~uSv&u^sVy+>vaW?OQO=!NS^7{UIC(kZRge#skvkw_k8e~E<G3o'
    'vQb<XPtrtdMgh*fP!lX(vt`EC`zt#D;t)!byVqY3lK#zWfNDQ;Dl6KD{nyquy!3QU_ga@calopxKxzG&{K<tRG;=^vL6TsH%$O8%'
    'Tgs=slgSAretHHaYFs|+3P+{|^1?s?^KUhCUHSbPA){d70HF8_{=oSKkHX~1b6FJYpc$ofX@6(%BW=KMrSDzc{hbONZ_$N9@q)?W'
    '^1|q_1ETSKjM+~~AcMumaJ!YI9y*c<#)us?5?zq8_0(jl(N5QKzFz_&Ta|j{1VmS*qLfhO>BxV!j{E7`=*^~a(%fTTY!0K_{@$m-'
    'o%YJkf`LATqPWtLQR=!j{nP7I?^E_+=zXfwj*aHD?}1xy87_?4VEux@yhzyzy9-=?5=@x*@&toum@2x$m}vt8b3J3LXc{?UU%}S%'
    'jBO%;Z)NNiyd=?30=ztASfWuzlbwb=8<!bIeO9|)4qypXu~!K?w41WFRC3Q|jyiUeL>vh=E^;No`zP!^)`uBIMHP<p7yZ&BY?QF0'
    'vUi<GW7#cbB{hB7tzP_8H<!QHg2Hl@1+m7EN4P<Gn+p*rE3C5gCKC3o^@<aT*;>|+#<2!avBj$&Y9WB-i~H<2y(>#<vrHaC0rsw>'
    's3~6B;(LmM3jwImZSnDo{fjakI(bh}yJ4#WUbYmCbuaK_RY{wJI+lVwI-=ky2MX4w&j<9uv^2u&)vQAoNxDQ)h4=kR?SJDx2VhQu'
    '>>d%~kn;yT57Mxprtu>i30TLZ)oUnPgA1wlbiw4&0;|TIEx@)4g%(x|!`Quyh+3T1Y$>`m$fJ+G62mjAx`pI&OABw`)tQPHAW1vD'
    'z!9ZeGf`MSe)1w{aih&ef-HIGKC<!jy=rTLvReAhwv}yrd+1V9T!&p`OVe%B(D&#S_$0a+?hKYU{my2&ilt3L3@3^|9;kCQlkmg9'
    'RGI{*Lp`HfDUNJ4$kbTj6|iH6J#>yxBG2&6dC)ifdHIqmr5L7piMTT=Q{Jn=>Nzv9003UTE{KC%5cM5f!}MpOL1g4*tyTUsUuqfd'
    'NKr0xE=J;?C~e)ofen9?XqE#_M*$x3c<15YTN~%d#N}GTteWg1xxw6=fCM_%$uogb58e}~7yU9lb%uoqb}ME(Ed>;>obaK^rm$2B'
    'V(fC<1v$4N2xz*8=2y81Qp&c(9B@F&+UQ(L$_|biF{T#dGbdGH)kf*jLv^`rgbfA_GOIfQlucm9kyg@8c2PWh`nJ1mrz-jSIabN}'
    'C&)v$OeNfjFXQrZ@1m%A3uou(PM%k^rqu!!aOPgox@n(kw+nA`hci+9>Itgb!2k^{PO6l%wHFp0h7-ldovPPlc#XqhoTyv^&s^yV'
    '!xDrOZ*~onhiTX1juuhCE0vX9Qua>AjrY-366r>AE8J6^LX=@1h;}em_OwD~j^u?Evy$DB1C4eOqSri<6x2s!(5TtaAb#XWl*oB2'
    'Qe!mG9cx|ic$aNRF`Ek11?x*0w#jr3R>7A89><aI(m*JWe;|4;RK3L=v=D1sa*+BR2VG7l*Iac<^+N1|mGAh;ON_kEJanugq4sVr'
    'HH{l)4#<W=y|z+~LQ7~b>Q1kAX)3#V3+Tlu0OsXB&jn%S@+{|E0XMEmmW$ABjiqrZcP*8BTL&VS8ZDENI8A9qOYhweyK{%Z#xtG8'
    'b_PM@OevWS-=(P>iiKQgmbU~P;Cy(@eWjEf3$^wdi$TRkh0?-zZ%<UK=It1uJS|67UdgcUG#%Dk2p&unVJLYMw?T8c8NuX?<((8>'
    'Jjd8f7T*+LKaA=NnWgMV3vh{E^Eu?fv|@J#bZ`TPUu_w6Mko+0I)MvAO^3~%BDIS?yoyaa;Z#CBsb5L5e@{XgiO;8iw$+DCGmVCb'
    'pn|NdHcNB!k{WX{wPKpkgeo(&xX06@m&2;I(7?`k0$ey@qfMNuCmt?}zBwCq<MF2&5iooFheXNnp=LGHOvN^qw$SOXBxdr)5{;Bk'
    ';~I_?0m1nH#xS&E7|1WE+<MI$mq2K1Ic)*c!g{@0WFJ=&54-H2Rl&%vLi5T(83<@H*zj3`v<c*J3`qw46c}BQ&5AT(9y~@xqGsBz'
    '-qe*W%@M*C>L^p==4^_H2uiV*!qmv<>r61^*Zy#vmsekjeOGI9r|SUUask;z5RQV&2$iSRz-yCDWO%<0IF8Znsh!65r0@X-zpQ8y'
    'WKs1HDSlq4I{oR%T_SsWKBBMTSB|i>NM?|t3K2vu(3{gsR0g&<CDA^mb_O7im8>F2Qq93m+_(38DmeLsK{^0`MW8NdFnX>WG;k1a'
    '7SHJPrzVhtSDG7F5C_75TE;+U<ZOZJkioz40NR?A1hK>NMkJMyO<Y`d1#GM?X)pe?VgK}P_ytP9^@$S&J~V+h6I`kY2MP``SCsN5'
    'tAaYpz!1{5E`nHs7KU{*45kVWAq0EERNOv&F_o2AE4JVY2mK5}_PArVK5DDZ$<9zByd4C2+Mw^n4<EW>N?2QqH8R#Utnfnay9_bi'
    'CJfH&5sgwt&`~?SgihEcksLNKVn<#l$2;s4o;;f2$Wl&rB|>KwOmj5^xI(wi2KUQxibHC900QEChu%-(U{0iW&~SJv6Q0Nw8JeXP'
    'o)9ABdXxwg1Z`nK&kO-JNYnGw(b@tVh~Co@?a}e?;x~6~I3k;svRACxU0!*jpWX(gZGgzL2$`*+izP5$=E?~%p^@7e8`%w2HEd=m'
    'shvM&K-)g!s*<uniH!oG2ZTD}=Zuv+S#E=Wa&cj`o>R}!moPC=21oifU1WmC1I>@e8<WIi@vcazsi$>sY^Eu<5oE4kM{W?Z6oL`j'
    'XBc7aYg-c3hB>W6G>-f3*o5$>@b<;?1K_N`Ism8KD721oez``Rj`KKZN0$bK5&qO|7>CU`z&Ko!(jg>SU^oY$QxuscsM&O$&H*eS'
    '1ORA)woDm7zLzxvRh_gf+l1x`xY=Ohh^sV83Mz3ZL-#<<hG2@F$f1G%pRkE^AB7BGfzU(L=ofTTC7?iAguq^}p$FfnSu=Wy9r960'
    '(Vl<n4*pJ2TVi7TnD#TO>&s7I(9;6j&4J^!Ih0v4XbT=*N3>!k+6h;AanPp+Hjuk;Jdh@T*vp|G-4xu+fW{4)zLcJdu%SqTL3dn&'
    '(^6oyZ_znmSPXGYq=o5SbTS1@z!+xbv$PzNyT!=WcQ?21kEt-cpwNS02!$34ErD-h`?dM(PW&gk$2QLbm$z9R8c<jf8ZJDKL6?p;'
    '{zfW>K5p$Ab<yZM<|JkHUM}`<<yO`(^G0Vf18P_Nmg*j9Y_OXST~ju-<CIOm6+G4EdFFjq351D{tzr{idO@TvI;DjKZd(68L8@!>'
    ')gV-~Ylx^NkD*GKQ6Ef|)MrFJ)?ABTNUc&G;iIIiz#1L@mUY0uee(<EUCqviNqOiDZP=#YK~&=)*&Lb%*Ct!-Xt|z-tu^Ra22Vss'
    '+cHAXxY)-jR~s-z7l*c4xsYNChL4nMhD?*`W2G+zrW|d4t;`Ut;*VxV&enI8uv2Lt)r3jByMFG2Zy;RF)gdt~hBN0xt%>xLi)IT^'
    'ebqU?>g3T71R?TW>+mmvVAIY!36>!hWQ6Q%iDW%!7fzhvjL{6{e=<cpG}TxdW(+M!C8J``f_=!k^m%%=9X75pW;yC`_+<?JK~bP2'
    '`~>z3E75vcwk1>740)I2{#5uQCAXq2MX1czx?3Ynhp8}%0^HNic|uS{DK@tU-4yYuK*K+8fBc7rbs$y>E_+t74KaG$#nBo{6XG|K'
    'AU!~?j`Dd&P_2h7?`DI^tQ#|V7bnT&J$DKv4WU)e)HP+{0HqR5&iKiuYzJHuT+24W1ruTFoqA2?K**6pFhHA}xk+Im*Ak1^vy9Fq'
    'h*sbo*xU)$FKH2^^VmvoEd<kxotwb9W}QTG7|GCE)CAc>DFfrYC6uRi%7bMB7lpAzHWB&=+YX+hH}C%Bd9VuC32F04nRbO{*6eVC'
    'xQ#5M!u#Z)1f}U`Wqns(cu(8Sp0)%85iF;~lWdtG$edbFtN^Q$wuqinhnc>g_9R?OfZa<74ze;)3WhC(_rJ+aGaW*G%GH@NoW1-g'
    ')}lgSp(0fngI_Jmo(up^6_}>Q!u8-wCcIgZXpA}wpC9d$qgJmZ3`_&|i}8R(fbuNcR?6UjWB7CghG~%zXK4JEEJCe;GJ5{LiUChA'
    'aqhz-25L`>tWu-NmSd0VHu;N841x)Rt^1#gR`}DJPa8WaLzL|%O2ePl&w^Kpgy?K4Oc!`l+fq`Xk`&V_?PgRkOl^cpeEcTJ&1h|e'
    'Y%E!pak&FG6q(n>&@!~OPvA#ho*gPR4oybC5DS(HKZyZRGV_x*!FZn=c+CDsadql?S8Z@DmL!cLH;H{*Fw}Ju#wUcl(`RhI^E0@4'
    'I;Ey*U|LTfdoYEjjc9jSM%(Mbsf-BAu|qkOHz*o>^yo!$`^r26V1q1<h%}x<nN*UOsU##5$3gti{4^j8p;EKeH6c=>Rj_0sKTNdB'
    'fi_|<hoTGSUWUD(K8}IWh12?zfoQz2Mf}V9<j}|jb!bYmfwMwC#Z&xI_bJQv=4du4A5{gF@^sz_1ZL=gvE7jxftdMce#97jpa>RQ'
    '0;2`kTjeudE$M5W`uf?yd@&q9<cPI9NlJkgp0L93%P{Ro!xp?LcAYsUE2o3FjW>Qv0aNh&eH5cTGkE#+S|2wj08IJlq2^x5>P)&8'
    'Je8EzOZU1h2c!b|IGaw%1E~~}*~VE?tidpks1nL`HDr}!5P@)s*)|!Mw>5>!5eOzeoE+cA3+Q7Tv>=O30kCrTV5+FiC&70tF^7|0'
    '#h^$?V{tdJkrJ5Y8o7m27Zh*PU`#r>D`hkWGF$r&fi;9Io0+(7Ca95cCnB$6V!bD&GEOA1vn{uVC~8UI?sZg|h1nN|CFxnwIAH*x'
    '4QPOy@$=Cp>T5tPUL3h;Ww8by!6<ii#7i&;j|NdOnn-R|DM$_`PDTbTfcX4k0D`8)m<pOyI#hU>)rMbj7C~+a$+(t+h(KJLg?KHl'
    'f4tcg2B!1!fgcypU#|{5HzjiF8RwcjZ&F{}WqCd!Fm)YK#l3G!mem8aXII8%5bk{zw!L!B)<mBrZo2YdtuYADLCh?H3j2K}e|Q$C'
    'H}LD5B)eLLSfg)>%PPGR-@90fxk`e1)z`5M(u;NSF_;%8jY&XJmNF}rmz3U$l-@}noyHFO5=j*wT}L;_LNDUH59hd+F<z`okR_+I'
    'M62G&7!ts#L;bb_@QLq>G%r&GIEg8i29B|aElA*qBYVQ4RENaBD>0Qaj6E}epv>Tu`hG6q6qbrZT0+_z8;o$uvHml3P$J(a7d;5Z'
    'NXk^zII5)aiPCY$5}R2QEKQ%o1Azr(hRx8Y$4{_bF6J}sen?&O3=l-;pLzI}mi&}aY|LsFl?MGRf%{A~LK~wNL<C}yF2WKJ;EmIz'
    'JJ>l^QLd9|AEea44`&}z`w-BxQGuOlg_`E)2(%RDErb;bV7OrXAe%D@a*z2;nK}={PB7Ft{sj;^$)#oH0<NZTr{nBIYktkbsiqmX'
    'S72Zurk-!iv|W8C1oLTHsxp;$M^F_6B4zStkWs61F0GK;7}}^ibVn+EhK(Fn#9>NPyHmjvBRg6%VIUvN5eaSLGRRec=U_%cGh(UW'
    'sA()A46%56E9i|%5G$8xlHti>K@Pc42mnk%z*~x{D?tJBgbo42<{vkWc0o|`<+lAGxf&ML226EQH?6HFw$nS)5I5rQ;3Zr}K~~^R'
    '11a2So@gyA6OR9`_G(f6Qw%D{6hiGY;6o#`HpFp7y?9Xoms5L&xS2qIXrepF7*Vc0Cc7RPb7q8S4kb(B#c>ssxT5SbbWHE1GGIb!'
    'F(iIGs>Z*FUH-s>NYF5|EQ?H%G-JFfTNo)%5^PKj&!eMbwl=ul)@cB;eRvRMW)CkyI!3oq?cqDdizq%L3wpex&TKODJi;x_VF#Td'
    'eagb^=`%=P>Z=^L6T_988NbfE4?yIJsm;nhJXc1F)!NIOCDCEu2MR2ok!f!6>kQ#a%D8BDN$G6SK(ouGl$6m<br}mWsMXcjfj<|X'
    '_0(s`nNF22V*O;4V<|)3F16=bT4M(sLYc6{_Q;m`Eh%UdDgINK9q@H?Hp}BH-+;AYhzj>u5y4_r$8-LAUm9i9%4P`-<$|@}FvgP8'
    '67FG=>=R^tpOoc~?|ekiT`~xy9MsDc<b|U{gn|&VMzNPDilb~GH3dEbqL!&aYQ>KYO@Nf<b?w^}Z63ow+K@+@ayP|>3^ICAdyzJ{'
    'i=jZ&H8&2ClXGGe5|2L3Vtp~Ho5m;#4gp${&!MBI$SBN+WnonquM(awK6h@PWhDpXb0)(Pke9`%GFvpzdf?b<U>b^zW}vh`M`PAv'
    'UMP@pG@b<;6sOIVlU8FBL}-24Y+3H<zF0Z8x^PsyZOWq9{YcDQVg#fHmQ?M2729Ab8LFBfv)ag=B5@spiAfLhy?>J1%yDwBn$Fo;'
    '9Nnc*1<f-TNn%7qYSV)Ozpe3i9}3<&ISIa7HH?r;dYog1KYv|dBb<Acl0!E7n(%du1kb(1)(d-9JnuVuaaXY!wr1$ljq+wVy$<WT'
    'L<tYid)=>9XC4Gvq%7!`<SB;(7G)!dLJC)sC<VWlR7VMesrz(XR6NyCs+<g4*Y(pmC~CFDZ~gk{@jm<umrnXe'
))).decode("utf-8"))
_GOLD_HAZARD = json.loads(zlib.decompress(base64.b85decode((
    'c-pO7+ioBy4E>ipk0QVqpl_{|s;g$ZQo7QrUG0}t{r4s_Fc-kalO|GLVh<SO%dt)Vd4T-z)A#QWzdpTu{q+3l@28iC#Xq_wy#Df!'
    'AIk%VmHzFwr=Pz*EbbASpN)Iv1T$yS_auK_>5b%fQjkd?ldvTndy!0HnG|JGl1W)4v6D$&CIy)UGD+43%i3UB8!T&sWo^VTv;wU3'
    '<gWJQx%pZA;#Wp*WeiqE*_0B>B$7!ilcG#YGAWCs>|~PcSXp+g%=$%nCx7c5D6~$Ou+zL2BNpMK;D#T;;G;nMSBS%}4hAJ2d6Hew'
    '6DTxPXe8@}lOpUg5c2JBU%ot-KOLJy*`Ixk3N0x#Il%ek<U^%S!H03BpwK!6AD7lU>WM}QjTKr{Xi28!pj%k*s9XEzPtU(^f8yht'
    'P0*Iq*Z@3I;fHdt-57Q~29#q^K>5A{X7Nq~IfW+Qcc7rq<ogbU3XK$6ci)GK`!s)|ZD;@d^!(+Ii*qew9hWqI;^+Q$4;7Wv-Y>rr'
    '$L13E1&^=5?O#P1NQ4*^8pt;pQNFFHXgw-gkBZj&=o1fGmT7(TInlgAyIg~NOjk^c3oq2T-05Rb7B+kQD0`jOiQPI9uvt#$=s9?U'
    'J|T@0jCTX$Vl6&pIg5qN3Qf8GoMdy$a`FM^#P7g)Q5JAA+5?yG-Qe3d-rv9VJ(i?nnQ=bJqXcjqG|<(Sdm9Lw4FHT0U+Troy_oxL'
    '0mRvc1#bh&C=pObiGU>EE3!h13QbPr&?mg(w0*)m(Y!(nVw3=iV`tQ~&SMaKFvK%(aF5-kyr~yA&TQpOVGxFd4#0A(*l|GR*iJU!'
    'z}iKC5?-%+_BOrBcv_JbTwq%ObvHW9yiM(cM1Ze}U|lp1Vc8o=DZe1gum`dXdmy7iBZbC_EK&40baHixj+&!GtF>MC=;Dl5zIk-^'
    ';;_WO)4H97V6|clc(M0R0^TJEbm0`!DTb@F(E>#QVLQX0UtfOy_RG`D%U?s;;vrjZ7UHrHxQQsR<^JnVy>G(N$n&=_g`_Qf6*3rh'
    '4#&npsNYF;$m`-FKI;P|LcX?xx^MmF(ui)th?UV#7^yM_D<fDLal#lYBh8v%v6ya2S_2$|r4So<@8qu2e%Ga5yYe6Lp_FV_axW`x'
    'HaLsQNNmYZ+~%i#!#r}P;kFjBYHwHK<H`rd&LuL=I78)}8Uj{MHgiTZXPR+R<;*kA8f&97bJ`+YwJzOPP8U76mwMn*MNi^A?`TE2'
    '>U~MH#c6j9)B=nfrs-0{8&kndXjN1DsjTo6V>Be;#TG=?^+qYVPm~7^DfrlQr|aCynNV^AljVH3QrHSjG09aA_U+3fQ6{<S!7Mjc'
    'u;NJBIX1<U^ApBU8H449a=jpOV9Fxgn6IQka@gcOtkA@S<C+n~-kPI=oadVIHh--8@;sTz?x2r+wAkiRpVcL0|D?eTXRsu7OUlTf'
    'g0s|odla?8hiSH?;7yhkrVAPo3x)6=ST9HaY2c**wqEC8;?M@AWQ|GGlw8JRcFTdkA}-~WG&yC!^Dz~X=4a!HSMM@KW6GmaH7YGN'
    '4CibwV)G;Vn@VFU<>&k?Flfn9eW4+@<OrgeNC@PX96^_y((&wrZaM8V`XU>Qb!Cj^>Sbk5W;s{(JTn5mB0kxK<=VF?VFqEFN=z<|'
    'PpkBovhshRHmd7&lQO`*VGu`&`jmw=e@?}p38v0hWy;1nh<IAFRGVUNtZs;dd3P|ciN<=3m@HaaEG-C{SDyQ>^I5~ZNJ(|Ee9L{K'
    '`=BCeU+|;AMh#ps*!nfE+I(v(ni6S*L1%N0gnbsPO^W!QrjH^b>HXYp+Hex3eO-~oEV{QR4QX^*vR2Xi+3}Gom8UJFJZ+&gn7Y=~'
    'tki~-nqJM`d#03IN+^_UeQQU#iK=o}PI+4D_6ng4MCQp+5iM8IZ1|x@t1?rWRHsKVljRwRSX~{al<%Q{OSLL%GFIu>UFQl?HPH1V'
    '+D)#n2L|J8_O>d$BtrINJh(A_vyax7%j|7PZ7sT1{ygk*rxIihI|lcjVa%WbLAH{(0mHKSa`1Z9B2?i@LybeYf7s#hP`>P7>cjfo'
    '&p3QgmsL<lU&<!i@PNVF#!?KkX%ke&*|do(BU-nn31g~^))@msG-ehCV_DTE1Ywf7KApEdN@oOHt;k4LMm8BDn7jRkB!Hu?;44bp'
    ';@5oidqM_2ZP0)**?O4KdXQ=FmAc-m_PmNQ+lKqhV7rl;4cHb+La^npT$eQtX=3F!4MT&QPeZF|ax~g-8T-u<`Q%QqGvXb(Gv{0H'
    'f~JiK0~q6B3Amx*MZr*Tc|EGc(dfs;R#&*N@NYFfXs?=D5C_AjH2zxXT%9Ifo1KS12|uVhE)673WR1azKWOV}z9|{)JUh!P3meYL'
    '{?^;N#v@FiC<pUc$<)E%47O>~HBF341#O_p8Q+zjgeW7tOlstd_J?Ym>5g9S%DcxGwJ@&GC6An8_@2lRvE)(0sqxS?Ml?-DOVIXh'
    '&^8Px<@BAC{s!^V1>u}+ZdmjkowMjWYym#HcfGk215k8eUT<YLjcUV<_q(D=?$7<Ax4zej-oGo5D-JyiiP48!^Kelkv4g^5W{Vzf'
    '4a{%sxwq`1M{7@X@GV)Klv*b}(8{?hX^suie`Ms+vDOGuMQ{5b8=CnhTX9CTy`1oKfZlGo-R0Z?{{0V4Dr6P'
))).decode("utf-8"))
_WEED_REPLAY_STEPS = 2
_WEED_STATE = {0: {"last_step": -1, "active": {}}, 1: {"last_step": -1, "active": {}}}
_SHIFT_STATE = {
    0: {"last_step": -1, "due_step": -1, "due": {}, "last_preempt": -10**9},
    1: {"last_step": -1, "due_step": -1, "due": {}, "last_preempt": -10**9},
}
_PREEMPT_ENABLED = True
_PREEMPT_THRESHOLD = 0.5
_PREEMPT_FRACTION = 2.0
_PREEMPT_MAX_BATCH = 30
_PREEMPT_COOLDOWN = 1
_PREEMPT_MAX_CLONE_DISTANCE = 6
_PREEMPT_START = 120
_PREEMPT_STOP = 680
_PREMIUM = ("STRAWBERRY", "MELON", "MILK", "WOOL")
_SELLABLE = (
    "STRAWBERRY", "MELON", "MILK", "WOOL", "WHEAT",
    "FERTILIZER", "EGG", "TOMATO", "CARROT",
)


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _step(obs):
    value = _get(obs, "step", None)
    if value is not None:
        try:
            return min(max(0, int(value)), len(_ACTIONS) - 1)
        except (TypeError, ValueError):
            pass
    day = int(_get(obs, "day", 0) or 0)
    hour = int(_get(obs, "hour", 0) or 0)
    return min(max(0, day * 24 + hour), len(_ACTIONS) - 1)


def _copy_action(action):
    action = copy.deepcopy(action or {})
    return {
        "farmer": list(action.get("farmer") or ["PASS"]),
        "hands": [list(order or ["PASS"]) for order in (action.get("hands") or [])],
        "market": [list(order) for order in (action.get("market") or [])],
    }


def _farm(obs):
    seat = 1 if int(_get(obs, "player", 0) or 0) == 1 else 0
    farms = list(_get(obs, "farms", []) or [])
    return seat, farms[seat] if seat < len(farms) else {}


def _align_hands(action, obs):
    action = _copy_action(action)
    _seat, farm = _farm(obs)
    expected = len(_get(farm, "hands", []) or [])
    hands = list(action.get("hands") or [])
    if len(hands) < expected:
        hands.extend([["PASS"] for _ in range(expected - len(hands))])
    action["hands"] = [list(order or ["PASS"]) for order in hands[:expected]]
    return action


def _tile_at(farm, position):
    try:
        x, y = int(position[0]), int(position[1])
        return (_get(farm, "tiles", []) or [])[y][x]
    except (IndexError, TypeError, ValueError):
        return "LOCKED"


def _trace_actor_action(step, actor):
    trace = _ACTIONS[min(max(int(step), 0), len(_ACTIONS) - 1)] or {}
    if actor == "farmer":
        return list(trace.get("farmer") or ["PASS"])
    hands = trace.get("hands", []) or []
    return list(hands[actor] if actor < len(hands) else ["PASS"])


def _weed_repair_action(obs, action, step):
    """Replace a blocked BUILD/PLANT with DIG, retry it, then catch up twice."""
    action = _align_hands(action, obs)
    seat, farm = _farm(obs)
    game = _WEED_STATE[seat]
    if step == 0 or step < int(game.get("last_step", -1)):
        game = {"last_step": step, "active": {}}
        _WEED_STATE[seat] = game
    game["last_step"] = step
    positions = [_get(farm, "farmer"), *list(_get(farm, "hands", []) or [])]
    unit_actions = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    active = game["active"]

    for actor, transaction in list(active.items()):
        index = 0 if actor == "farmer" else int(actor) + 1
        if index >= len(unit_actions):
            active.pop(actor, None)
            continue
        age = step - int(transaction["start"])
        if age == 1:
            unit_actions[index] = list(transaction["intended"])
        elif 2 <= age <= 1 + _WEED_REPLAY_STEPS:
            unit_actions[index] = _trace_actor_action(step - 1, actor)
        else:
            active.pop(actor, None)

    for index, (position, intended) in enumerate(zip(positions, unit_actions)):
        actor = "farmer" if index == 0 else index - 1
        if actor in active or not isinstance(intended, list) or not intended:
            continue
        if intended[0] not in ("BUILD_PASTURE", "PLANT"):
            continue
        tile = _tile_at(farm, position)
        if not isinstance(tile, dict) or tile.get("kind") != "WEED":
            continue
        active[actor] = {"start": step, "intended": list(intended)}
        unit_actions[index] = ["DIG"]

    action["farmer"] = unit_actions[0] if unit_actions else ["PASS"]
    action["hands"] = unit_actions[1:]
    return _align_hands(action, obs)


def _shed_access(size):
    half = size // 2
    return {
        (half - 1, half - 1), (half, half - 1),
        (half - 1, half), (half, half),
    }


def _projected_shed(obs, action):
    _seat, farm = _farm(obs)
    private = _get(obs, "private", {}) or {}
    projected = {
        key: max(0, int(value or 0))
        for key, value in dict(_get(private, "shed", {}) or {}).items()
    }
    inventories = list(_get(private, "inventories", []) or [])
    positions = [_get(farm, "farmer", [0, 0]), *list(_get(farm, "hands", []) or [])]
    actions = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    tiles = list(_get(farm, "tiles", []) or [])
    access = _shed_access(len(tiles) or 10)
    for index, unit_action in enumerate(actions):
        if index >= len(positions) or index >= len(inventories):
            continue
        position = positions[index]
        if not isinstance(position, (list, tuple)) or len(position) < 2:
            continue
        x, y = int(position[0]), int(position[1])
        if (x, y) not in access or not (0 <= y < len(tiles) and 0 <= x < len(tiles[y])):
            continue
        inventory = {
            key: max(0, int(value or 0))
            for key, value in dict(inventories[index] or {}).items()
        }
        if unit_action and unit_action[0] == "DROP":
            deposits = inventory.items()
        elif unit_action and unit_action[0] == "PLACE" and len(unit_action) >= 2:
            item = unit_action[1]
            tile = tiles[y][x]
            structure = {"COW": "PASTURE", "SHEEP": "PASTURE", "GOOSE": "COOP"}.get(item)
            if structure and isinstance(tile, dict) and tile.get("kind") == structure and not tile.get("animal"):
                continue
            try:
                requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            except (TypeError, ValueError):
                continue
            deposits = ((item, min(max(0, requested), inventory.get(item, 0))),)
        else:
            continue
        for item, quantity in deposits:
            room = max(0, 100 - sum(projected.values()))
            amount = min(max(0, int(quantity or 0)), room)
            if amount:
                projected[item] = projected.get(item, 0) + amount
    return projected


def _public_signature(farm):
    counts = {
        key: 0 for key in (
            "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
            "COW", "SHEEP", "GOOSE", "PASTURE", "COOP", "WEED",
        )
    }
    for row in (_get(farm, "tiles", []) or []):
        for tile in row if isinstance(row, list) else [row]:
            if not isinstance(tile, dict):
                continue
            for field in ("crop", "animal", "kind"):
                value = str(tile.get(field, "")).upper()
                if value in counts:
                    counts[value] += 1
                    break
    return (
        len(_get(farm, "hands", []) or []),
        len(_get(farm, "unlocked_quadrants", []) or []),
        tuple(counts[key] for key in sorted(counts)),
    )


def _clone_distance(obs):
    farms = list(_get(obs, "farms", []) or [])
    if len(farms) < 2:
        return 10**9
    left, right = _public_signature(farms[0]), _public_signature(farms[1])
    return (
        abs(left[0] - right[0])
        + 3 * abs(left[1] - right[1])
        + sum(abs(a - b) for a, b in zip(left[2], right[2]))
    )


def _shift_state(obs, step):
    seat = 1 if int(_get(obs, "player", 0) or 0) == 1 else 0
    state = _SHIFT_STATE[seat]
    if step == 0 or step < int(state.get("last_step", -1)):
        state = {"last_step": step, "due_step": -1, "due": {}, "last_preempt": -10**9}
        _SHIFT_STATE[seat] = state
    state["last_step"] = step
    return state


def _repay_shift(obs, action, step):
    """Remove quantities sold one turn early from the scheduled SELL tape."""
    state = _shift_state(obs, step)
    if int(state.get("due_step", -1)) != step:
        if int(state.get("due_step", -1)) < step:
            state["due_step"], state["due"] = -1, {}
        return action
    due = {item: max(0, int(quantity)) for item, quantity in dict(state.get("due") or {}).items()}
    market = []
    for raw in action.get("market", []) or []:
        order = list(raw)
        if len(order) >= 3 and order[0] == "SELL" and due.get(order[1], 0) > 0:
            item = order[1]
            requested = max(0, int(order[2]))
            reduction = min(requested, due[item])
            requested -= reduction
            due[item] -= reduction
            if requested <= 0:
                continue
            order[2] = requested
        market.append(order)
    action["market"] = market
    state["due_step"], state["due"] = -1, {}
    return action


def _future_base_sells(step):
    if step + 1 >= len(_ACTIONS):
        return {}
    result = {}
    for raw in (_ACTIONS[step + 1].get("market") or []):
        if len(raw) >= 3 and raw[0] == "SELL" and raw[1] in _PREMIUM:
            result[raw[1]] = result.get(raw[1], 0) + max(0, int(raw[2]))
    return result


def _remaining_shed(obs, action):
    remaining = _projected_shed(obs, action)
    for raw in action.get("market", []) or []:
        if len(raw) >= 3 and raw[0] == "SELL":
            item = raw[1]
            remaining[item] = max(0, int(remaining.get(item, 0) or 0) - max(0, int(raw[2])))
    return remaining


def _preempt_shift(obs, action, step):
    """Shift a bounded part of the next scheduled premium SELL one turn earlier."""
    if not _PREEMPT_ENABLED or not (_PREEMPT_START <= step < _PREEMPT_STOP):
        return action
    state = _shift_state(obs, step)
    if state.get("due") or step - int(state.get("last_preempt", -10**9)) < _PREEMPT_COOLDOWN:
        return action
    if _clone_distance(obs) > _PREEMPT_MAX_CLONE_DISTANCE:
        return action
    future_base = _future_base_sells(step)
    if not future_base:
        return action
    hazards = {
        row[0]: row for row in _GOLD_HAZARD.get(str(step + 1), [])
        if row[0] in _PREMIUM and float(row[1]) >= _PREEMPT_THRESHOLD
    }
    if not hazards:
        return action

    action = _safe_market(obs, action)
    market = list(action.get("market") or [])
    remaining = _remaining_shed(obs, action)
    shifted = {}
    for item in _PREMIUM:
        row = hazards.get(item)
        if row is None:
            continue
        target = min(
            max(0, int(remaining.get(item, 0) or 0)),
            max(0, int(future_base.get(item, 0) or 0)),
            _PREEMPT_MAX_BATCH,
            max(1, int(round(float(row[2]) * _PREEMPT_FRACTION))),
        )
        if target <= 0:
            continue
        existing_index = next(
            (index for index, order in enumerate(market)
             if len(order) >= 3 and order[0] == "SELL" and order[1] == item),
            None,
        )
        if existing_index is not None:
            market[existing_index][2] = int(market[existing_index][2]) + target
        elif len(market) < 10:
            # The target is an opponent SELL on the *next* turn, so this order
            # does not need to jump ahead of our base orders on the current
            # turn.  Appending preserves the teacher tape's same-turn SELL
            # priority; prepending can accidentally let the opponent beat an
            # existing high-value STRAWBERRY order even when total quantities
            # are unchanged.
            market.append(["SELL", item, target])
        else:
            continue
        remaining[item] = max(0, int(remaining.get(item, 0) or 0) - target)
        shifted[item] = target
    if shifted:
        action["market"] = market[:10]
        state["due_step"] = step + 1
        state["due"] = shifted
        state["last_preempt"] = step
    return action


def _safe_market(obs, action):
    action = _align_hands(action, obs)
    remaining = _projected_shed(obs, action)
    market = []
    for raw in action.get("market", []) or []:
        order = list(raw)
        if len(order) >= 3 and order[0] == "SELL":
            item = order[1]
            try:
                requested = max(0, int(order[2]))
            except (TypeError, ValueError):
                requested = 0
            quantity = min(requested, max(0, int(remaining.get(item, 0) or 0)))
            if quantity <= 0:
                continue
            order[2] = quantity
            remaining[item] = max(0, int(remaining.get(item, 0) or 0) - quantity)
        market.append(order)
    action["market"] = market[:10]
    return action


def _terminal_market(obs, action):
    action = _align_hands(action, obs)
    shed = _projected_shed(obs, action)
    existing = [list(order) for order in (action.get("market") or []) if order]
    existing_sell = {order[1] for order in existing if len(order) >= 3 and order[0] == "SELL"}
    rows = []
    prices = _get(_get(obs, "market", {}) or {}, "prices", {}) or {}
    for index, item in enumerate(_SELLABLE):
        quantity = max(0, int(shed.get(item, 0) or 0))
        if quantity > 0 and item not in existing_sell:
            rows.append((float(prices.get(item, 1) or 1), -index, item, quantity))
    rows.sort(reverse=True)
    action["market"] = existing + [["SELL", item, quantity] for _, _, item, quantity in rows]
    action["market"] = action["market"][:10]
    return action


def agent(obs):
    try:
        step = _step(obs)
        action = _weed_repair_action(obs, _copy_action(_ACTIONS[step]), step)
        action = _repay_shift(obs, action, step)
        action = _safe_market(obs, action)
        action = _preempt_shift(obs, action, step)
        action = _safe_market(obs, action)
        if step == len(_ACTIONS) - 1:
            action = _terminal_market(obs, action)
        return _align_hands(action, obs)
    except Exception:
        _seat, farm = _farm(obs)
        return {
            "farmer": ["PASS"],
            "hands": [["PASS"] for _ in (_get(farm, "hands", []) or [])],
            "market": [],
        }


def _kaggle_submission_entrypoint(obs):
    return agent(obs)

```

## cell [15] — code

```python
import base64
import contextlib
import gzip
import hashlib
import importlib.util
import io
import tarfile
import zlib
from pathlib import Path

_AGENT_B85_PARTS = [
    'c-qZ<XSbqQv+(!+71}Bnw4Ezv#~ct8vlx4|NK#Oe1QpY7e?jFO&*?Dp+<QN~XU$qIJ5<%KU3qVqFJHfY9dN2hSz(sbggwW47?Gpo',
    'u%;-I2dCC+O<+vXFg4DjaXLq74DVqmnH5;d;QspZh2S}lswu3=7=j{u42@zq&w<jNU$V|<0&Rm_X*MwGK0^2G1zn&;&LhYkMYboK',
    'v?wq(aEFM$zH}6iu9%t)gi%<|qi7z@lnp`Ro+E5945#ZJLHC$C$NuH<I20T-N>w?{L$R!GLlrF#Z`1gN5{0!aakBBvLo24t+N9W2',
    'C|X!l7)taUIJ?0HO9|RHk4~*P&k$*~Yz9!0D#+_^9vg;dCCK(ro#)suqOdcab=%AM>x<2}FM^~hn&F`-olC~uCq_{%_xDCuWcT+;',
    '6zDHszL4cA(dc%Dp8UP{FHxab9dtVXVmU^URGZB@_yGAAolZE7EC+&LJoevzF=1_+>lWtG(st1zmy6y$m1(bxGZ1P?)k^g|nQtux',
    'ZZ;yFX`@j>fJXNaKzG;8?2s0QXck(PZ!Iji;qXl|Tv1iHU!|CRwopEm7_kQoxL}8c{_BB?lR$;(2`C`qGx4M;!yqt{vRra=$rvGD',
    'o{H|rxqMPYLRQ)zKesL;nVFsr^re{`VkK&><VFE+CXj3I4#Kjh2d~zo(_SwIrFpvm&1Vrn8c$|VR9JpjIjrIvqJj_Tk-EG_3r8hY',
    'JP3If?zKxyct7bYvZCjSOr0IvPOWGGE>#;$fp4bB9WfctOQ8cpWc`<H|B5aQs+m7t*IrdXm*@SYv<z5W^oh!6K-MkX*5&<TJm@Vr',
    '8ZSfyBN$F>I$pCyD#A@2mMchz6^5kuOq-ZL*K4;<GTH0O?Z~>^>Q1|r3A6Gqh!KAXhcB44>p>H1Kw?HWuxu{5$<akMS_U*`>P>IY',
    '9nF#(JW_%~bi11gR?K6PW)j$C+rYwHe>Rf=!NTAXmkuA($I7LX#rJ@)pX7*Pkfz4F6AL8=Yb+!7Bf8i^t@Li$+0I+rdgO@;qVUo6',
    'fD4$K5-<^^!+S72JEjA;-njS)njde*bj};Et_MufG}pt!spl;ed}ddN^@_R9wHnzS##42LTon&JJnZ*xGt5H0TtnSTsm?9uL4kdu',
    '3MYne_;~FwR>o{;<V;`Ya%LAercZm8LF@4~1=p{8fZnKKtx|x-rCWGlT+j;|JxbiACx|#TMGSFS8=TMbMBJT4e>%m8fpA>AG}`ri',
    '^=v6mRF&plfe<;^6Jq5udk9NQ9+E5jzACcW{2JSvh5#N``%KFSp#H(WIG^VG*X$^eEz}ml9x~f>QoBrcM8+aR5CnQ1lw3@%5vc&3',
    'OTC)Z4dUV+aTz!*sYo|@X=>FCdeuAi$Ud6nCm}fiY}xn_&uooAYd*U%T=;-(uY>CzJGHk+DRxOWBz3J2OL*e%pAF$AkAg-BwRUw(',
    'F#N!|Sc8{?5gDo7!cSBexF(eH7@BCF$w6R0FJXr2lck`4uNC&$%`N4RZi<=s?ikr8_Iwcyj%MS-p<3wV$uM+G<;oIWuBLjH!h{3p',
    '9-@vh1!&iTO9f^^>-CAT_}t`)Dv@n67FjRv^{sRiNbiv3n*x!7rm=3~)(qiQZQW`KoVtvy3Pcm(R#ZM&j!dbp+{@JFeP003f^_>B',
    '=FR!UcgTeE-R!7-f$>RT?XUaGx!8zxRrpZJ+>$<~Xv<Q*A6BbvqQxnzBDl1y<qACxsqVf4ucD{yel4Qe%P|6P2l>+tUsex3i4Ju)',
    '_=UkcMK0J2=tyYX^Rr5xw=GSgpqE)?8y=zl<P#N*UubXq6y3y-8iHN*0G3fQiBxf1=9k5d)}_`eeXOwYZ4VDDWYF{{!&J%;mZQ@w',
    'n7HD4JfV-fiG8DalvncXaGjS3RI8$VeOkzN2LRh(Cz&Uz;ANPj*anIe{ITdLnc6b&c08w(wX%L(N2vqF7b2Nl(5D${I1L4kqouAT',
    '#?^FdkCe84O(Y3@o=h$ylNAq`1dit;J$lzwn8Li!2ZzNim~6S`RshP;VIK_!dF{O0rpf`^?skr+_4Q!Qu#Lp==z66TkE2?08k1&h',
    '1|ef%fDn=GB~MJ)Xvq)q*UtC=mnKxOdn!rfDs`Bj>1k<k2otegyJ?MGu^?CTb-4!?)#+T+m%wPzj8zH=yp)51(GE{%5+WS#)Wkv)',
    'SI3bZmh;wu#8qFU+wpN^Wuzmt*r}drx-#i_x7aAKtEpM0xY#7O#eHTi!farg(4VN}j#3P!q2;+dN+YVc-0xE-Xn-;aeYHx@DYKct',
    'kFioenbxglQ9JNRdQh>w#?k~z*gSL&q=8!ac4d#93l28BYTRh^-tB33o+M1Dwxt66?U;X}THbVjta$Nmlp`-@=QJTER(J)ac+%Vz',
    'o25Xq1k@$jUxLz-w|=SBM_8=Iic@5?0gC>-*$~%-cCJjC`D(J&igVqr7#{oMMRUlq9g_z9>S(!qqMB0dL5W7Ix^A0TfKM#LwFR5A',
    'l`=_LNE7kxwO(wSiwuO-v7Zg@u}jF>+}1f_v9kSFG-~0AESX*rg=C<|HZT13Kt$0^f%Fa4aXunIK>`rCCn_}6xMf<E=4v0pDFrlg',
    'iBMx0Xb!z$vFOLs$zGYF1Hl0YwUw|gmRjVwTrV+%0sB`zhUx4=TTmPZ#YUZDpykxN$A<-ijkmigayq7$O*ur!rzfg*K@9l>Yt-!O',
    '+VC7(My9}c8b9o3NSE~S*&bRWeP|BbYTzy|kisZ&fHpZx0OP4CQ^;g%;bXEfpG+g+88%vMdibg{5vYnf&J@#~NJ^5u+M@GBm4oJ{',
    'jC8;pIF1XODYD>3g*+|wCQT+6PNzf(Esp@EahXUKPi0dOlc1<_wX|8T=J9SL&!-l#LXeA6T3qT6#{C{2^Y%_hj$h=)8LQd_=L?Q`',
    'qGI97pjFAW`{L1TT!)T%qnn&q^>=DmVijq_%H?#O^+x9rmfGZln{d^D1{$#Nm*i0;rL!UCI838upv>3vdas}I5>c<N(4~p!@0QFa',
    'Aj50vi7JF^{C3=}nd=xk?RAEi(8BN*r7S`=Za!asXhFUCzAH-A9@L%Yt71rpt1M7!9A~)#cd40vbIY_l-DIrM0CPq$io;gf>JRb=',
    '+OaJ(2B)>U{6w|hq2hq^MlR}nv1P(A5}c|;HSXn?!n!c#TD#ujcwAiv%1tVE>!<a)?>hw5RgBJBN}@SBD5t{Mm)!zWxP|QUqk1HB',
    'tn91Y*%~iY$~*1cpcv|^uqo}4zPD-(O*x(;$1RR0QlnEkU=*=_Wt_?~QjF@JT4+zmb~}w$F-T>50bd`Xxt7S)GPktp%L9G33xF|f',
    '8O<jTT6y807o`aoMG7&r?nA4tWf%R}YH}IvLJ7niYG`@iVvQ!ZFP6LO7%IwmM#3`m5J8LM))m{|46&|BbTobSB4*Q9Qt-TGtNdOw',
    '(CfI)REF#81&K}8ZDE+ak-{y>%D%u86`nKZgh+y=g(Y&LzuytYfjyy0&BSqbxxjp9n#;9gE&s3@nlw!!CNC8r-)Wq#Rc<}ff<CN2',
    'HCYB^Xm2FtO-qYxJboDGkF8+@Fnt>ze+W(RC#uM}6tyP99CF_EX0aI_fdajHf8AZ3Quwu(NW_+8ULFfJQ=;akZ~1vy>cP|4p}*Vb',
    'Q@%0<PmI7$HZPG2)9muasmu@OqeH1HSM@VfjHx>qb@d8a$k~K0r3#ZA(x-T@hygM(kV}zHNw4R`*=3gT2B3p7%C{D$pt>m~=;(T7',
    'k)s1&3&hI!e%(v>Qe+92h)|4~FAhH5<i?#)aXXLn=Oe9>5QHbHVFJL?`}QqkN~{&^L<_S;MU6)xe7A!z-!LHcww8INjwz+0aa!aW',
    'm><C~KAgvD>|l^$E}M7;Iuj*uv?J*q-s*?X%}#om$aJea)X1^hQYw3WqAHDm>}u}C*A2Y^9+h)pmx<NZBpQrjc&^|LS1_<O5<=Q)',
    '+^?dUZ5VD02iJ1)wAT)ZmcEJ6nE+mB<$RIocz@H!=F@XDCk#sdbY~Vug$hk!ZgAF$R*natS8NYbAu*q7UlIbg*Us(C0o^o33#^rL',
    'kQXoZI^3buYLCyp;jxpD3eAPmJ{5(i%A6YfKm^TY!dJ7PON>I#@F_B=EXgFin^g5`X6$An%M%w!x5~lekU30!z~scArh&v+=#12&',
    'dfT1$vE<4-E-+?fzY^j}tTM=jsfC{11z5feYzFnnFc^*-6j9{#a)z7w@gy*S$>IuX`3guWmr4(sPgLc3h{vZ|02tPJ->E$l7jzPy',
    'a0hKtR1+CYByX!$W`#DkLt_x@ho)BvlW?t84lG-TL#tCgEuu7|!H}XcF)|HRS7d+I4S{nKtQTsbLl3aFpc`9E15_SZRa0JolE<Sc',
    'P#X*mfniZjt|+h8g0jgSQr+n!7L8@SgQE~#R@2jN7&&tRRj`Il1fZJRk+#lh0JO^EC2@3xV|r_~^+VCoGF^;Jrw7+x!SN!jHm5>0',
    '17`+R+@G|3iWUHM<Qh$c6)t^)+oxWCqNyvCJWMja1h`jbdaZW2p_ZOk(fG8T6`H|{08u@zY$baf&E&bjc2-;$!D@2ILhuvSBC6#0',
    'jC2}QK-hNTQh&l9DjmpLSH}BeezhqI6`};oIvUcpK#TPs&SN|E0B59~C#Oq>fMMQ4Zh<Rdv(qJR#Z~Vl$lYL28H~N1X`M^dg^6pJ',
    'Cbjhpo~0sQZC$U)2|KsNQv;)B6479?W@S^pWi#2*q#?d6(5HA9mv829510#mY=sJYYEta>yLoSCxJaExjVidE57wMd-|n{ua+~IE',
    'NDhs;`PIHp=cYYFGuZZ;53YJ%aSHB@B~o3U3|}p4KwjD!?`AO(_njuIPOYD<iAlV6maUy>d1L(%xu!}CB`WF>Kb}zFY#Y@9n$0iv',
    'tt6pi0e?5`u8LUed0ku&%Nl237&WWwmr$%1I$suWQ7<m=5nml)L%LUn&TJ}z)zjoTuMF`mHod`gvfiAjj9*zzOGz+LndI@dHmseP',
    'Gf#IrbJE|*ly*?jjcyn4Wk<pYF~m3R(Ct=c+NMM`y|YHf3Nkq#Wa`C4@w7{m5pW}dokSl$)lVcqP?yaa9!taEuC?O3h01a4-JFrs',
    'G9O&rC@`=hh?zHnljo9Oa;=3Dm^HVnWvfi=dK05%yJ~xi+)Fiz3xo{iPt(<56Qr<O@d_WUbc!s-$B20>S^UX5S#~;AOyo<)U<oi3',
    'Qz}J|e(Ab5(sZmDYfYJRaWo2Chb{v*m2MzAhdLd>V)MmVB!4o>!_~w*iS&War*mGq!F4kiD894Qsd=+))FBQ}>Vs;mf7w{Vh-(%0',
    'd>&b3JIc~d{uj{FtTftKFQ=xgIZ&Au`)|dB{Yc26la!C4D`&ovGEO}*Z6^VJY#qhK5*(6JNGIOQp>jwKYDlb_SXc3COj(q26cNl8',
    'E+Jno>ZSITjUSk0CY7*o!*WpzEckMJ4Wp_NO+OT#sPxz^S;>MesU6!K8q$0y*Oc>WLv0%%&0no%+&3A~GpS0O6iyCi=R>m*632%|',
    'IKQ=`Z96yxHo1(sUqnp++V{&!=UD4Qd_2D$6o<{)F*@e^<`Y$+zy@wxIcpJ#RQsrEhFK6|5u!DRl#$$9m*Im*3x_xm$zF&Cax6jd',
    'bpSkGyvx36@u3(2&-{g@<X<&IXfi5o%EzVJ0J`PMVF?-i9#)>f``Q!L$(xyT=xW&>au9qtQvwfgt1#9;@oLVyvGN+x+7Gxgf7o9w',
    'jSa!$4B-XTWp~U4Dqs!p4M~553Ke;LHabgI6c9us){2#4i%TZEt@g#Ow00BJ0ophRTj~;9)kd9W+`pxXP4XgO$)>Mh9V=)QNU~K(',
    'Sg}}RCuxaRN)_4!k?)_Ia=y?x?K6=`Y(yYuyc$R_?ZnD^ZL8fDyp9JAix}x6bGLE}KOJ0)9Fcr8TddwVNLg`mra0XpKC&J3A7e}o',
    'PRxkTEx`IZSClZg$r?T$56S$h+9m^jQ(4oAG<UtFtWid!1E#X0uWbZG*h03T&=kJVB!9H>L^TFi)f~L{$2-yEDVWYjtu)+M0S3%e',
    'N_8MK>Vqvmd7*{+neeeF&7v5zT?IF-{bH%D=~bCTyNy*}G#M$gwbrFH6YWj-rQC!i?G)Y&8x-AfV~eUSIQ}lzS#9dmzBVtxQlK0&',
    '6%*{W1KWkRGreA_+gmHgk_>JSA-TNd86lJ@G>kRvjcym`UN<QQ4p?1{@TsuKD*IkfWPH;duMpOL0q6^B{6ytF*0k<CcvECvAg1uf',
    'H2EqL*-tZllPZ)q+AJJPCbdEtNjH;=)-+#&`RtXG$nK$b+bql?vbX%T3S6~w)7?-La>-*<_ksz+pvtswIuV0P#f>fcoL53K%<&>H',
    'eyTI5FOe+_7mvZn!MD+3gF>pD&J=P~1C)Zz375UZvjaTV%J1_vSf_%a${;#MQ(~||F}X#k17GZXjJJb(a*H%6*<A19`dD*ox7b;P',
    ';=bG@Z(UBITdSYC(S<&|El;7CZyXB|q8aJx(+aSW1H+PS@sY^1jY!hOU#@I~oi=BB!E}Xa0pnqMUPC&KbUCx@&iDgo;pf2IcQnwn',
    'n;ww8cB#wlC&O?a>=gt7@2@3#bn9iS7FgmY8)OypFAl8WCk9(SQVgHwf!qksHw@Tp4ll{nh+Q)y)EB62qbgv^<7R8tJ`{;GlkS+)',
    'Vh#k;u3>6!*z_tz1Vb&HD(5@0okWadd;W|p5VN@2UrJ3MJzo;Nkx3qs?X41uG@$mr++D<Ofl940ELw_1QQ5h#TG8o5E5Vh{)3wme',
    'riFt)RI8%WxJo}!sq&@6Voayv-JU1Y^Pz{U+cl?vz;PN$mLwpWZGfrbavSk;R%y3tcg(6}6tAbsp}Nbp>ro&fC`z5@rX5+$w@|FR',
    '?<{r)|FAo)99a!YoU@hf6IJ%sAd3+RmNDOP2q38oJV8RacEd02>}0dSKtaa4K9?esdNU6s;$bX05P`tHB_s$i9m|!l;As<E?sH7A',
    '8C&iS@g#Gt^npZ~05jIDbljnO#Vsa;cU*81D7AytLTjPs^YMip@|nUo=-o;CTtQ31i{RYy?IoStZn!Sm$Y_`0XhiAT>?twmkAbLP',
    '7!FQht6H0M1Gz|}o}SA(?@cDONNE~Asr|I&MohR4W3{2Ui#N{7AV82qeS%jiZDLrt2!&3&crjvlbZ>&O^I9K7)<CXWD=#FP?4|@M',
    'U8qO<c0M76NHCVJNnA_E&x^>iJxO=ix;!mR(Cikbo~Tkotl85}W8N6n&{RE9B~u9k$%aO`d3WC23d$)S=?scxn8$6z+h*J9=4MM4',
    '_Mz?K6jHh3cx|VAq-FFni;{l`G;iY&pKL6*vuL}wTn?*xC-FpOl&P6|^1|l?vXn7Bg^$j`cw#%Aly?yX8FadPpiU~$G7@i&XHf}H',
    'T*+Qp8{>&uZSK!yP8ExdSEHf!VPR+O$fVFI+Uvy91K-GyS2AT~NZL*1s?8M!B=q&c0G7Ana4ql%v(;N2d@SdDqCc9|<4QKWiuxxa',
    'pj9pf{Lqy)iN&!29)u`9>K_FftJ<EVk5qXx5C%u*h%f<e!{$EOk8}>{CO7T55fhXtSJ>(Cu!iSL83(rAaI-U$(E~`Aj4^+!Dy1TI',
    '<%-$kEqQCiwpo2YC|8f8h&Q-VCsS}eN7tuT)V~adgi|l!&m+ZKKwXqlTzVNeL@|WTyVV$--?srg46VI-FlWjF=2g(>oTy#%b8{aW',
    '`jGsD0+`KGDGaV&N$FMdQCJaHBX}ZJ;YOjvrE`;pP}(!pNf-PDeP*kEE}<atZTmba&XY=OxpC`(6(&W^)?p^bR|=CPS_rRVK_%fY',
    'l;~Wx2;*dD+0dmlUQ5|1xYKeu*er2;-ii2WJOS*wmsFuTTAl!0@q(LmVK`bSGk^bR>Wtn7x_$r)a>FMoxH~A@34BdTom!{ke!!FK',
    'RY-)7%i}EH<#{^|NXOcz*t`|?<#Ie4E!F)i7!9a{EwU(AQWbP{8iB36Vu!QUR8c6e&E4Xv`s*usXyzwYM$07KI1n6*IXNCwn^9sc',
    'qzJj@Bf14ZPc^_yHn{=f&4stYNA~e4P2_`}Si!puCHZWbl6z_h+nC#IljTc9aIap_aQtY7R+DoaI<=T4YX*ipq7`Fhz(uu4D%PAl',
    '$<nYlMQ6Lbk{Hs&5H6j(p(DNb_f8#)@a88>zZiwLh!JMgLuVL?di}9DqSeCuvdFf<-UL{0{n37lmi(v8AkE}9tMt5C!&}Lsnth@=',
    'pH`Cso>2W|I%mz>xl414joQ~`E@yR@-~x?|S8%#VcBFN1lbMm->5#Z>%y6#S=t{{D8b{cAeY1-t;M&<ZX=j1$mWX{LTif7s7EGpF',
    '>5|uVBG7sqzRkqrqO+|9QM{i-Ru`zP)tgYUTp>Cm20*hyqamDpaH}MZW)YL)z#KBF?)E}w*A;5>UfwsuZ$KUj0xdcatQy|%)VQ3&',
    'hPfC}(dbxr>+B&0D^HIzD7+cm^zg~{-Aw$b&pK7U6_?w5tr%QRqG;%(O)hNQ$Sy}lHaI?x0ZwkD&3&|GKw4~5vD$T8MXc<g4y{?^',
    '##cI#qY)?^TLRP|7Vfz)y&Dw^>ll%O2Ss912uad@TyD&~v1Gx^Px{GzK&VXu-qh;E?>DV;^33IPjEY`~BRc^@ZErQ*TrO8+-n(5$',
    'fj~YpO(oPx)~YVaP_Ed-Z*=diL~<*fVn`~nXAWDqkcvm3M)d4UnEh&by0hbdm^mGbv6;-P>1!aez&ZkRF^A_GUNT1ExHU8JARbDu',
    'Z0*!&-ES4_q|8XgaSHYO<ce}mPSJ~7q$`iSx8i15V}TwS<!ygkYb=bu?=nu&G66LGHGChRj35re?5s6{?FI=zzy))5YGNi4ipD3f',
    'W)gK}SB@6(U@)oHd8~XrZbJ<zSl+^my_Ko&o~ZbsPAkFV2=do)EV@{XrM-f%x$RLg4s>R6?GtF~f>sfzT4oBh`bwKsljcAOr08}f',
    'C935UHmLyl&}<swv1>I@VKZa18jIE=ad|*@&%q=&b_=S<zAw@Cn!Y&%udbuzWGCw&V}j|S8i4}ogiz1k#0hJlevYN<MrYCYAIzN~',
    '^D<LdlbJ!WyP8wERQ$wcq1c44f~3|AQ7APDq5%{ub(9GlUc176wbOeQjI88!gKSC)XsU}Oc`fw4W;%SRGL7|os+O+@wVGl5yLD5V',
    '$Ce~;5w7V0xT4JtGbkoUn@J^AUGwNIaGK)rCW17pTo!F6&Mje7<;zc0)Q&%eqlwnCU`)(#M;fw`F=l2v={S6Z2F3#Rtq03%t=Xf}',
    '6RLG;T>{-G*As!m0$0~o5s!Bn?@|n{cFXB@35>~NZ#~#{#Ra2s2tzahn7_EkFS7vRRjDmdN0U2HE&wI(t=rp|eY_G}_XcsrqN|D8',
    '5XA7gH6Ng3@)-2i=W?D2RckuM?!=-U)Rt;e%geN|EOrjo57(yYJB%0+Tn_lg0*RF3PgIR8Vg*N+7O`TL8M4_hna!{r0Nb>_3RlYJ',
    'Ww-5Or=U_;Sc=!bTxikc7~a7-K5#we<W6wZ)ki*G!XH~3!a2U!q}42fb6Aqe7X}+LqT@t|b@Qv0Kwffof`Sf5lTi)C)7Qp?hoi;Q',
    'O6i}X?bUUh$!)He4ehm)@71AwsQTu>u|d+!{yraP&3HL+Ue`+t{Y1j^R(`!lQk&z-VA~Am%cM3cRT%W$;&(Q>+!7nkWD$QmF<F|c',
    'qQ#bgT_(r$8kvsR+^*F~D-#R!&I84JREsU9Jkv)=REgC$lR|$Vp*nW@j3pQX-6Fow@De?2BI!m`+(j41M4<-(ZhFw<(#WYhAHjT-',
    '@zR$DN*w|)a=TrFw=q&Q1XkVZu-sZ=HSOw6^h%H(gf8Cpp^zwe6I}PiDM*MZ$3p!Su`lGivB<Wn5#vOtE>wY3#HcS)7uPlV_=UeX',
    'J{xRvt2Gm|w33pdsW~6)jg~&GP+Rib30n7Sz)Hww8cHMtrm9pX!BpjnKRNc&H2_7rWq2>2&2jaX9yN;ke0||zxpS%3kMf~W#)9rG',
    'l6b$@wMzbcRV@$+qc>{B`0V76rY&zWCkVcj0Ax3I0@0P_@ZeHw`^jamM$p8HnZ~z~+A<AEIkjsweEg^YX>EFws@_7BKLi>f9>kli',
    'brHuzS1jTNvyN80uy?g)EOq3&oD<k-Bh=G_1GAX}_49SItFqp@1kG@t7(=}hC#9)rqmd3I=<WG*@V2}aC?{34xe}eRhB+(OT2;P?',
    '#Wqp=%3b<?*Dzt%RxMG1xK?YpT0@0EuZIr8rA%aX+%7p7IxQ1z(AMZ-oy-Q(n;9@|N}c*ulTNXbUksP7vSMNNZX&-49*AozOSU?-',
    '5thjCY^a_)EtTzn3^m*`aWaYmDX*dXT3MPVOa0cafCe-GZ6NEk5Y1FB6e5;`yUJ|bj}MRzRjCyseQJ|LuAI6r5ayD%l|Q+owK)+9',
    'k*9Q4@tb>05@S7o6QojXHZgZgB-8EU)Mz9iO6XN*{={_<?IU<Upupvm2J(YrdghOxNxGhFUUg0`0^L|%3}@BWsd1GA;7ZLdExj%l',
    '+vs2wIG1lN{C4QHa@DI<k52Gr7Lgime${Li#6`cwW-eufqvG);a6K&#;mWa(nq6^CE)ggS1_m`mqqFol)zzkDE>J5`!BaFV<JbJT',
    'S4q{4v%bkL{E$z<BDv0-(9UwDG20qjS{HWG)II4*Mdzlr4SR+CWs<JKN{hhsqnh=%7j-gOiJykXcA_WYdIZI@sq1wi&|^7-@HkkP',
    'eVIb1XJOK2Um2{EfpKHB?<6>C*g^*bj>(V60E6=2$gSP#We_UIlYvAM$q1J~0`;elB4!8$ywqdjQAyqgPQlypTq_#Q%9>W<(cF2z',
    'oiGvQvdo3VGJ0GA?N&6JMEY1UiPaB&c?cyM39X-v&9y6jyDbK8APrN|p;B5~<z#n|S&}HYO7;(d+BwM!=q#I5d`nENt0}9PnJSW=',
    'XaUDzbk~?_oLWx>$4sQkqy{}YwM!4<TN<qRn1Ze!2|I43Cl~^wXoL1XQPn}Af$D{Mus*`VdZ9C`CoV|8hy~Dav%Vra3KU2zdiVzL',
    'a&7t`=1mbQF_kPg*bmwhsJgWp-k7p0GP@cpoOXd$?4WW-fWW)8rjR|7<GPP<i*y{drWg5TAm1y@^NUuJAT#N7hh8D^qSa{XQdZ`h',
    'QwFX>-cF-ityK{-+8#uet#{>37PfsK6{w{vwT>T64slR1QPH22a<q1pCVG3yY*w4x#T5%O0_sb-Q@6v=U^g2d=PppJ4kz<85pRQf',
    'YsMtcWIrn{5k4?tYwJb_&+JNA5mT=fEF8*~XZ&eXFcVgs)comit2~l2LM9OJEyFqgrF5<D*FD#=CsTDaU&s#@hT2t_Tk*ne1!8$S',
    'TA8+9V{-ImbY9CBVB9`+dNo0$ZzvXH5qj710@SQuz-Qf3XO*LihsAZCj46i@UJ8{ct9L2H7L96|wNA~mdkrUV8#*ivM62QyMY+T!',
    '+KP=0^@b@4DeH@`RsR|Awkr+)u+j-lWJTVYZIC+PNxsyZ@HKTxM<B4b<uc0vTHmWDc2%TvqXNA+O|E->*<SX_`zNYVyH`?CCq+!^',
    '-NslPrR$Z}H5`r4LNP3Nsz>JO<D#cq^X_DqInS6{f4ugsFsWZ`M^n*EnNGLrmDL`i*7-`Jq^m-C)#9yUp$P}9+My!*>x!H7WI8ev',
    'gmbGf(UAkG-E269x+j&337Kmw2Q-EaDurQ1Ez8c7HH^>p7q&v@%8VHCA}JXRuqJGaI1GVoIMbBPu}M+WnfIW<esQx49mbYFHzC{;',
    ')SNLBSSVk}OsjEpzYC<i%iOS%1yd;GWn0ZEq*rs}i8x4&+nlbQ!08~_v8s9~w~hyApej{w)p~7yTW`;$jg&JbO`h7(7z9CoJ+H!k',
    'HH}p`{S|_~kZ8A6BeC+lJgEIo@6)Q?R7g-NRvak^>Ne6J?^KaIU-azSKkqB4zBWQ5SL3Y3b+XQcx0Kkupsg{V8+HS%0gc%>5k5g>',
    'Uw?99Rl+>)LNT!vO$$}ubVnX6Uv1@DfpTLT7)#ixe$ev0QxKu)@=)zSjXg~GtszO7I9W*0fmMIAWs4%aCuG+0Mlcz@G*J<rK=FOD',
    '<_D?`3mT!dP&^h8VxvmhO91*rS&WH&_ArXM*K5|3X8#ya=jE(#q6R0NutS1mq*AE(Q(i%2P~QwKPpW$1a_cd}sTx`b^8SEaJ*JpM',
    'EqU{I&Csb8t#s5jp0%_7Y!=PR?O|mYxW@T%Gs-40&OL-p)`(+o%B4$Jv8#^O2`1XCi~@=g#=EVi6<jus+nAk2`Wj+@+vY}#z|f0D',
    'Viom(dz0l_N*om??Q4HS;M#dAMAKe%6W9jz%oI8Gj1jn4r7hlgqUuG0ja_hFiZ!w;j5WfERR0#u_;w4tkSL$0sm|`!SWQBG#!mNk',
    'Ib}_cVpH6oWCRGsmtGyZ%xl>ayYPach7jCwhYUa2HL{CP-yhGWCj0QLpt(hDe+!NwFtErcid|n1?)2lqMOrnoYQIyjW7G8^yxvyk',
    '8z8U1D^wy<AkmP;b=hjHZ=LRDyI^d49VNn%#DGp!Lfd{VvfOlqz8&$Jd&B3?>zU%nb>tVK6xmdXseddc0kyGC>^iajDvc^_*78%!',
    'dVAsPrPfeC(JYrkiK2yu`&^6-Yx~T&2?|A7?&s;|&Nj|F^pXRItdwaT;&qIOj6#H_Sfp}nxv{u3*fX$?=7DNn?a~4|Dj-PA%fqog',
    '-P3@gv<456AS8h^FDQ=>vAi%|8vPqEY*ToBj|V`io(OL(?Piq$qOW$x=&{bmeUUO46ffu?C^Sc|u%E61UQHCkfe=~gY87TrHfiFp',
    '3v}r{Hpy5*8)Vw>oV$)Lq6&|hw34sQIe2YKOLodiR!XSM=_-lfKs-WIm~h;L0559P3+-w?TN4wf#y0HMBeGd?(uLw!CN)l87?A<n',
    'kwIiZG!a^gEWLItT&jae!Pg(R`qRkBSamIOfG%r+QBluk_u6Kj8etlC?DzFSZqby-RsjV&ei_J<>m}J=C4(`IcVlrMAgj9Vzq5X6',
    '8Ls1vZ12)yrp4oN(U$6<DL@8a9F2Xch1Di&xmB%2i9T^w;nVxTK55wj2O0HWwD?fTmC`#i$^}p=Va>Q?OC{@Lk~&V7ZrG1eExq6A',
    'NV9q977%=1pLXqKxAjeBh8-|Ghb=W0Xql~iBbA1(>Cxug#?}HcpY{f!K`tBImeVUBlcJl;(CpAWb$h+^D3z2BZ8_NP2#a!YNg!^O',
    'r7*g+F&~rMWS~l3UTJzba!vzVnVoJra82J3N^)GNa9JOL=8KEaZZ_^ox74Dx(!{=Yp{kbL886D>W{k!98aCXZkqlKPN1@oNpFHP=',
    '-c)<zUdFRS`evmug>6GnRx6`47LRAB{KgigO#Qf)la2nCDy^BWu`QQ|xoSwhg}1#%-Ztsu2F8cO=~7lFPQ_zX3mwW^VW5tgR^(DE',
    'a>R6?o2l+dBv$SXxrlyISdl8Gd0~hZvnh+;YU6TGi5;P2en@06Y8GXJ!NU%zrnAL%sXXalP*gmmn**j!u-o!Ae4C(vRrM}vr`t3i',
    'r@Yv(-7eviBq~u@YW8;PDqa=n!x%!dW4Sc0k8%ZITda#KIm1ojp;E4^t+`IM)SG6K3(^8X;GoT^c6z*=jtYI+Tiq-QLwcK-Wc4%H',
    'B;<rtiENK}E<dgp$Mqdj@8nOpi)#bbZAIDhIzPZ9HU)_N?lL$=%_XqhNQXREDqhuCdLQ8@Ru-1|T%%kcpyN@;nCn@VjrA^!(8=Xv',
    'QVF9d1Pxcu!<yAEEE<X1ywe0P2$yM{-HO;UU#W7V&?Q@L^FCD%dgT=oYJhuC7LvnY3l4N5Ynj%2-NnS)*EZOKE@0D{8p60^jO&JP',
    '3Nk+T2l4)N5!?@=Qy~<)qKcFrHS5iJ2w2OhS^nmpb!>%OSl%_;OV$^OH9DaMIpX^Lkx#($%C*-B#cO0zUdP+jz8Xph?Q~-fUydaM',
    'E^3njrsHFAGdK)})7zO6bAkT3J8ZS=@T*}KM)kf}#CjO)9>RudkWY@bF3mLAEwKKIp*1>99xRi4i#nzPn@g%UPw51Fw$|IAc5DcI',
    '<03MfF%_85tul57BNB!WsU<wmRH8+p)Us%9wo2(fzPBv&QUyCkcCXg}YOKGO^j1zB0XeTw>UHc$-CM-B)4-Mkf)`c+E2FS1$KdsC',
    '0YN26N5dRn9g{TzfoF$R3NNb&+bJns%*bxzt+r%`=5lH?*jBulS<J@cwCdWxQbG~fU7L)~dl4uYEOz5KJMHJ|Qke-$WKZh!Ln6N8',
    '$0<$B#u<zbwWx)x5`M04O!Kk2H{K?Ievg~iFVyk24yTE*nOpV){T;fW(jdA&M=-ZYaBB*9<hDyzVrA(VY|phI!CVlO0oj$F9r%D?',
    'r(|2m)l@I$Yl$jZ-eA$waY_U-jg<o9LpXXd$2<ZhQ?bbarcU^zJHDPWmowBH@!noc;%2VDIu{q&j&EP83)P%DV*EJ>3B*&~!VRm`',
    'V{zEmCDn94blR-BNy_Moy1|mo;!G+e)|p|T#vIW@vjm{kWLZv=rKmXABM=zTcgJC|Ef&MI?zk~^EjzGC_l~(zrCdGh-o+R$nAgyp',
    'l{Q=D(B4dDmgK{j6}pYWiEWx25xH4w!;Ho`atGG(MSm(+KE_YnCaj=Jq84sig3ybny$hTZxBK{dk(ivvC)Y5=sdGR-9(GH(eNL68',
    'C3Fno;yy@U!SuPvPZzo=aLcwH+Sj_M+3uecbUI&^d19KW64nw{@YP&ImGB@kFP_hlalED_d%ug1CkRp_2S~3~o{>WW={awmMW4+>',
    'qD&z6^EvXj=loTqbc56lPW}3~Ck%h{e05&e+jI8Q`Fj24f&X#L^$R(~8g=3w?tQtx2F{w?=jS^V`{#YE9kg?jYTUac!C>b4?G6n7',
    'zXE0x+Z!NAyGM{nr(9_vPWnJ-CimV>U;|``+4+Ut6ZtFg-ccVs-r#ds`B&t<y<MJ?l`>Jq?2gz=d$nr==}w&S@W;{BR=0zYwT8{H',
    'PSs&q^1a_~8xYQvXymoA+jEAcA8qZ%sBJ%jUx&n?JgFdq!R)KO=r&@*z5i&maOdBNO~F@N8l1Nqoy9tH?)>~$6P<rCq)dE$?7`PM',
    'G9VhQ#vB<qT?mRg{}A1Fndmyds^!6;>kNjzeEGt1D-XHm3{asr-#lB+`sT5lC{r}@9YyA#zwaQ0l}FG8SvM$|;T}U-fia%F&Y#8^',
    'rY3vruD={;uYjO0F9YmO$}qH_(Y+Dl2#VdUKY{Nl(d2A?Jc-op1>8mHo99lSOWtFcpnGJ+xc9u1W@y&?!wV^rAcGQh1S8)(f^2|y',
    '2oUtmBXTn6z5@z*!X6lUo6Q{=PBlCrVW}LVX^QsEGj^uke?uR!sFbeX8(7M+>32}Ptif)ymk@!R_h%yy1iWHuKM!<TKac!*0S=C!',
    'CmQ#J?qGhsiYJ4e*I&uUyT0J#pC{#y2b%<Egl(%h)%o!p<DfrZKj1&Vt@rDS(j-o^6<8E><2mCl2yV}v{O@0T<>Bz_59r(bOy@OV',
    '-JbaUK2y<HPWv#_vr?P}r&*9aA3#5*J|O>qe!KvcC~eCbAEEvU(sTSLP*;~@&Kh1sQs*ecQT)4FeB3SP1!(SdzdU(oASddaCvu<c',
    'z|!s6cfwv~-rMboHu@(OudH@ZetXRQ?)?7Y;J(w5yYKY92YTQ+ztMevyPCYS>ABo*p7&+EZTGJv;y!|WN9zoGW5bt+E~p%1aICWy',
    'N7kIBI3vEfd-~H_?#=Gff4`BgN;^>RJ&?Uf7u&mz-Mjwcjs_>Q;CEME?wd?H8>~_Cngidc48OpGo=6@ve1GEqVUzanr0_oe``<3?',
    'A3t8V>H*Z<0z(ivl5#ntD!TBZa33tw@teoB6Yj9@5nEM0w!lB2&o=i1>m7U_S^wSo@%{MY%d7cn$Sik!+OK~yWltnuTiq&-)V{v0',
    '%lV7|d4E^ml^n+`e|x;X|F%BoTLZS_JnhhT*J3$Ka)v{WqWsEM{dkxgR}}6*9aVZWG@t3a@7o>UAI#1NDSR3Hle~WU4EeF+cQSsw',
    '6O?<E(Yx-wqk8hm`GNuY_=17Ur@Owp>UihEV>RxF9&DCT9$HkGtu3~dQKMD+Z#z8f5T1iz@Sa)&{pOISSsuaGO@rrT4?`IY?=e-6',
    'aS-e^IUhdwsNlad1aIc-cS^pdr27WG$D<GP<8F*YzOye8hi~_X++ALsc@N&c2ZP`2=ni_3tS9V`@!~^>KE$nW6Mmw?p6vj6qxAa=',
    'D5ul;aqo21$JzJquj=B8$v02%-5~$gianNX%7Q_<-^#Gz{leRQdvSG7$bWELZ=1E}o-6w9GT_IThtse}-bL=)<EtIdofYJFTe|1|',
    '5)4k#!B-Xwj-or^@h_F=A+pYPJ(SiC9^m(>tLN;(!@j?+`ctIyM6W6;_$2Z@G;{wLMK%Q4<lY*oHTT>hTj3oVUKaM<4)G|>`1)e&',
    '9QvIZwm1EV{FScncZz?wF6IM78wKZlU*r`iC)!}6o?QM8JLh=nkmu)=?B5{#ok4W0nQIhZ@ao*ZW8vHG-w}QDyg7oqTevR>a>Rg>',
    'O?yWvg9A^3`Zmb6Gat6?W#68{@Gc8)`+e8ur(`(K;g3S`m?+4uz}gQ^$o-NYxP*PX?*jBT;@SN7pXK5aQ{6|}?(aF%&Y<pwkhGPG',
    '7!437jk(*zuh2h$bNu0bdw%VQU(tSAhBM=t<~U1m9v|AfwfSNzuh(XtBPw72fr1C0T;Ji?yN7VU*}6B$d`8c28~bkgel2s~zuL~g',
    'H4(0yKljt=|1c|Z_gf!q*9VXFn}Fy84EXO4p7Hl?#ZBdS+xa~{2L$TE$;~EtN?bX*Z?|~<`@cQWU*{Cyeb`-n++Vgay|=!${BHcm',
    'vCyZ8Ue%P%J$Ad(`0A3MH2yL4RW)I6>)OYx^x0^Orky6egfDNX-YPE6pPl;t?fIO2K2nBvp>!1go+CfATlp@I4=43R=cL2-3SO~7',
    't|NFZ`QZrmoNNoAz<ta;-l4pV_&IX_C;w?ru-6g!@gMoo|8p05k9|KZ@3%qmlYsk&s`4KN)p2(B3HPz^Gv$7<!7nQD(e(c89X~tK',
    'H$L8Bf9QJQ|3BF@7m7{!8^EVk_=7!r_Z*<ZAUl#URgr`4l)TdBWLwdHpx{5xRcv}dXBOmI^e6M5&H;=#?$>%o)KB(1ANRVqA79(;',
    'd<Oa_4!O*<KIq)P*1JFG-pe+*hWHms_pW%)wZF=Yv#ghA$1*!XS#8kmeexwNcju*kXZ3SMKjFCtG5-R-?Jujy*L&}$cn)%8@Y9w%',
    'SU#G6dpkdjczRZMPre^NcI$>_GWW02IWDi-o!IW}>x=syVhGav)P{DuL&RyTc5Pl<@0#uq@^NSGX@?8kS<Y{qw$t^K*UslZO?IU3',
    'eH0}N5+#0)Dt;+rzbq|2JlW3V^oPNBMC_G^QQHDNOB<gzAolRb@CSJRNx|{ARKAE2c<1N0*V5q|xp(z-rOai$lb}P;w?D<MKjFOF',
    '%KO}%N!fjdbyuG!6`yLc&Q}ccu13O<i0#33Qv%<-=3jUHbJCiRQb0+HDLZAjPi5RUln<T$cE|9O06k{^%)d9Z-<<_G0nj@kuPm|i',
    'ga?S%*yU~LTa<DCaw4hQQ4-|{+}$5Nca3po>p#Z?5!dqE!`=@Bx>f%768>vh|Cc8PALlz-_@;Vq`u6RE4&GJo+cUI%pZ^+6I0S0S',
    ';ZES6-R$2VWa4fyoXVUt_rr;T-Qs2okD%0U`0@AWP5XU-{x225Az~$PBKt@w7)^1i60XwQzaB>7XK3yrgl#&&H)C;!WKa4EL4TRf',
    '$1OqVr-|<;6Y_J%e+K?84d3r$e|SRqPiDaVqcx7&zKYztfc$d}_S<jAn)0LCMB2*3+DWtVyNUOZ0eli`%jl0+VbvAQmi=ch^qlp6',
    '>LA()Ey)URXGm_C^B)$(pVsqP@ct00Jb7|ILj3Yr=gN+AG-1s<hT_-is6PUi-*v(t>+tXVrf4TrTp5mg4L@)=kly-3wm}cRkAmMv',
    '!5>CB#?Bc<+5PmR&P;vt&<;bLRQ^6W`s29@$A3T{`Kt56$|-p{0qC7^FBQfA)j`D_q{FtCL*su}{JYQmr|O>z{+H#y|M<Z8y+-&G',
    'wRg3(alJ3<w`D^2u;o7d$zP{-YdyI9=gO_5>^axrIcb)z*mlPGe(oJ6M`@z<_{^@sa~_?sGY(U<V}$z$Z4F9&FWbH`{?}Xk<-JPs',
    '%IP<jJs9njC!EJmxyT=<<UY-KVc6TyAKzY@?%Z=W=zRUGgwIoud-!oTooB~&eh9r?PYpr8ix`}M`y;(yKj*j)#E<hkCzJf~?xCoI',
    'Tc-MS%=cnb-WU5g+<BTId+vwS#j!ZgL&STe<^+!SXE(TZcJUEg+eF@xJ-Xo^cMU6eBEJl;-9cY|7eBtR>oNAt0KAWOzwG=7h2Ca=',
    'b4YoFG0<<|hx6~#KSqr1%-;{Ox$+Lk&e0<O(g(ZC@Z{g;zYTb7&|l7{qGk5U@ehTm=MMh3v&Q-P<v$kEUmnw~OvmPv&LwnG=R{El',
    'U)0+*bs^h8KC|_=)2g4m&l?uq6dj2?Uq4Ia+vM*q)E~b*h5q}q1UgdrE`RpZ&(h~K+OEdN;$A=beD%R0>-%HaV-K8$JN`%GGrD~d',
    'Jg5Cl?4GN9OnbMH5+%rjy#8G^?QOu_4gbFO_CHnLf5o6*YT#qhpLp~n_ALi^Wro}NF&%ig(D1L=_K9!L>F<TeyC?f+2QzdAI0u8z',
    '&!nrAW_Xm<-J8hV(RgtwHcUw{rH5<z;DH2Advi0-fcmFvR&GV+(?zFT-gWUGE<63K056vRUwX1%nfRB3q0ixj>-@hxo&Vi){dAe@',
    'Pjm^tjz?`X{fFCMe**YoKJL}xUt5z`w!aMd6JVY?Q5yR(O|)|(Tdx1Ur%^Ad*z2n{cWyb!ifdt@Z*Kv#YrOAJUM<DrWBQ^(8BRXt',
    'gsF}${e0c-wXFPD%#+IBE#%W-wDTQ*@}bQ?EB~7(|Ec2p$vXaQSN>py9@6Lt;iC-yZj<k3;FspoVQb!9+Am5`4<0&K&OTl@`}Hvt',
    'rL8%)TJd4%zqBpTx8Kcrk)(f~_w!xIpW(t!Y8*oYzRQDCx(a%Jx?~BxqWHj_=bC?x4SwPdceFR#**N#S+A(M!*#thiUdr%qw{hMJ',
    '@DCCBl!gCi;hP(gInDR|{>UF^tADfHPmB2FRm67*|Ne3Kk4Hr0@cp;_j$3~4^kePUS>1ExwjqQ+G23_l-)}tk!X}E6J&LN@RLO?x',
    'AnraS=<qyvcNMmIR_r!Ge{kayI9A~vOOu`dIftQmHm0O{D4wHO#~(SD81HuQK38|aGp43-vhfL)gY7Smr+kn195r^{1?057jlr2@',
    'aFp%Tw0nB=Uv@@CNnH4DSRBGXfl@U=(d@(_>%efqG1UE_L11mvlxQblqRj*c@*4|iCq<^@PrzK}dw4tR4nHb5@Ab8(=y7{a_8gr1',
    'H-=(Ef64tmL8COzW6BKgTu5X8`h_sK0q^&RAbxx1LXS=R@gLP*|2M(Q1K&Hkr@?%K^dfwY*M9VVxKi-z82$U-aOB6A-)5BVHIUca',
    'C!fOiC$7)kAHsoOW%3_`{NFjAzyFilQvXpX`~OE?`tMWEe>~6l=X~@(J+XL&9{JGwRtoqjvHiC`^QW@^8_54z!s<@{KT8+hN+AD>',
    '4ESBUetiLz(<JAAko3P6d`H6njm*E<&iw!I_O-K7_klk?z`IA%PVn~TqCY@<L;J7Q;+d!`2mM_^Z7;&y?-1Ner7!i;Hx+%mX7RZ4',
    '!Q4+gKHm6v2~ynf@;yd*d&lEN7hWa(U3MJy{z|I9{7Rq;p2*`Y)Is<>V*kLo&&O^D-4(KDjQ3c~3qtsD0m4ol!Y`|NFVVS~tpm!b',
    '{oBI6w>>_WcV5%^t<b*hQ^@oElfQETKQD2AbN>6eD(K+*@jK|BoBpgE)S8oxm!pUe=I>G6et93|lcRI`es{a~!;Sh6<sRp(;XN7r',
    '2<^|M=3h+sV<z=+=s(pN{wL61jsSkT!Ts~~#s|<pnWN9?<Dc!()6pRJf9$SzjDNhl^~<|vAKzhdFCKk5J$-vq<>z+|{^`EcCrIzF',
    'r@ZvM-A&t4>$PYHM<y)^x^AzGw53$DR7Ln8tgb-6$?%u|2Xq&oJO'
]
agent_bytes = zlib.decompress(base64.b85decode("".join(_AGENT_B85_PARTS).encode("ascii")))

assert len(agent_bytes) == 28715
assert hashlib.sha256(agent_bytes).hexdigest() == AGENT_SHA256
compile(agent_bytes, "main.py", "exec")

if Path("/kaggle/working").exists():
    work = Path("/kaggle/working")
else:
    work = Path.cwd() / "v13r3_notebook_output"
work.mkdir(parents=True, exist_ok=True)

main_path = work / "main.py"
archive_path = work / "submission.tar.gz"
main_path.write_bytes(agent_bytes)

# Create a deterministic single-file archive with main.py at its root.
with archive_path.open("wb") as raw_handle:
    with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0) as gzip_handle:
        with tarfile.open(fileobj=gzip_handle, mode="w") as archive:
            info = tarfile.TarInfo("main.py")
            info.size = len(agent_bytes)
            info.mtime = 0
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(agent_bytes))

with tarfile.open(archive_path, "r:gz") as archive:
    assert archive.getnames() == ["main.py"]
    assert hashlib.sha256(archive.extractfile("main.py").read()).hexdigest() == AGENT_SHA256

# This self-play checks the runtime contract only; it is not win-rate evidence.
captured = io.StringIO()
with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
    from kaggle_environments import make

    def load_exact_agent(tag):
        spec = importlib.util.spec_from_file_location(f"v13r3_exact_artifact_{tag}", main_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.agent

    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 93001}, debug=True)
    env.run([load_exact_agent("seat0"), load_exact_agent("seat1")])

final = env.steps[-1]
statuses = [str(player.status) for player in final]
rewards = [float(player.reward) for player in final]
assert len(env.steps) == 720
assert statuses == ["DONE", "DONE"]
assert all(reward > 0 for reward in rewards)

artifact_check = pd.DataFrame([{
    "main.py bytes": len(agent_bytes),
    "main.py SHA-256": hashlib.sha256(agent_bytes).hexdigest(),
    "archive members": "main.py",
    "self-play frames": len(env.steps),
    "self-play status": "/".join(statuses),
    "self-play rewards": f"{rewards[0]:,.0f} / {rewards[1]:,.0f}",
}])
display(artifact_check)
print(f"Generated: {main_path}")
print(f"Generated: {archive_path}")
```

**output:**

```text
main.py bytes | main.py SHA-256 | archive members | self-play frames | self-play status | self-play rewards
0 | 28715 | 6f52902081fed08bb5da08d575b796437e645c5320662b... | main.py | 720 | DONE/DONE | 67 / 67
```

**output:**

```text
Generated: /kaggle/working/main.py
Generated: /kaggle/working/submission.tar.gz
```

## cell [16] — markdown

## 8. Takeaways

1. Once high-score production schedules converge, the market queue becomes part of the strategy.
2. One-turn preemption is easier to audit as a bounded shift-and-repay operation than as an extra ordinary sale.
3. Earlier does not mean first in the agent's own queue. R3's `append` behavior separates same-turn priority from next-turn preemption.
4. Paired-seat evaluation is more informative than a single-seat result for near-mirror matchups, but fresh replays and seeds remain necessary to test thin advantages and tail losses.
