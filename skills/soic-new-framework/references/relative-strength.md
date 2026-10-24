# Relative strength

The video defines relative strength simply `[00:40:03]`:

- if the index falls 10%, the stock should fall only 5–6%
- if the index rises 20%, the stock should rise more than the index

This is not RSI. It is **return relative to a benchmark** over a defined window.

## Formula

```
stock_return      = price_now / price_at_start - 1
benchmark_return  = benchmark_now / benchmark_at_start - 1
relative_return   = stock_return - benchmark_return
```

Use adjusted closes and the same start/end dates for both series. A six-month
window is a reasonable default; record the actual window.

## How to use it

- Positive relative return means the stock is outperforming the benchmark.
- Negative relative return is a warning, especially when the J-curve is otherwise
  strong.
- A stock can have positive absolute return and negative relative return.
- A stock can have negative absolute return and positive relative return in a
  falling market.

The video treats relative strength as confirmation that something new is being
recognised by the market. It is not a substitute for the catalyst.

## Tool support

`--benchmark-json` computes relative return automatically from two price files.
The context file can also carry a manually sourced relative-strength record.
The output is a context field, never a stage upgrade.
