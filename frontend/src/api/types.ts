// [OPT-N4] api/*.ts 共用型別。後端回傳結構多樣（各端點 shape 不同），
// 這裡刻意保守使用 Record<string, any> / any，避免為了型別覆蓋而
// 對每個端點手刻精確 interface（風險：與後端實際回傳不同步、維護成本高）。
// 之後若特定模組需要更嚴謹的型別，可在該模組內另外定義並覆寫這裡的別名。
export type Params = Record<string, any> | undefined
export type Data = Record<string, any> | FormData | undefined
export type Id = string | number
