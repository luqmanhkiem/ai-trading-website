/** Keep navigation bounded to observed candles; price transforms never change source data. */
export function candleWindow(total:number,count:number,offset:number){
 const size=Math.max(1,Math.min(total,Math.round(count)));
 const shift=Math.max(0,Math.min(Math.max(0,total-size),Math.round(offset)));
 return {start:Math.max(0,total-shift-size),end:total-shift,size,offset:shift};
}
export function zoomBars(count:number,factor:number,total:number){
 return Math.max(Math.min(12,total),Math.min(total,Math.round(count*factor)));
}
export function priceZoom(value:number){return Math.max(0.2,Math.min(5,value));}
/** Axis drag scales around the existing centre; it must not translate the price range. */
export function axisDragScale(initial:number,deltaY:number,height:number){
 return priceZoom(initial*Math.exp(deltaY/Math.max(1,height)*2));
}
