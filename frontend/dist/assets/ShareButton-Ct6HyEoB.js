import{c as n,j as t}from"./index-CinKQvdR.js";/**
 * @license lucide-react v0.468.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const o=n("Share2",[["circle",{cx:"18",cy:"5",r:"3",key:"gq8acd"}],["circle",{cx:"6",cy:"12",r:"3",key:"w7nqdw"}],["circle",{cx:"18",cy:"19",r:"3",key:"1xt0gg"}],["line",{x1:"8.59",x2:"15.42",y1:"13.51",y2:"17.49",key:"47mynk"}],["line",{x1:"15.41",x2:"8.59",y1:"6.51",y2:"10.49",key:"1n3mei"}]]);function s({title:r,text:a,url:c}){const i=async()=>{const e={title:r||"거지세끼",text:a||"",url:c||window.location.href};if(navigator.share)try{await navigator.share(e)}catch{}else try{await navigator.clipboard.writeText(`${e.title}
${e.text}
${e.url}`),alert("클립보드에 복사됨!")}catch{}};return t.jsx("button",{onClick:i,className:"p-1.5 rounded-full text-gray-400 hover:text-geoji-600 hover:bg-geoji-50 transition-colors flex-shrink-0","aria-label":"공유",children:t.jsx(o,{size:16})})}export{s as S};
