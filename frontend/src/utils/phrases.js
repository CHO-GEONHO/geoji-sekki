export const PHRASES = [
  '월급은 스쳐가고 할인은 남는다',
  '오늘도 지갑은 다이어트 중',
  '싸게 사야 오래 산다',
  '거지도 안목은 있다',
  '통장 잔고가 날 성장시킨다',
  '아끼면 거지, 잘 아끼면 현자',
  '할인 앞에선 누구나 평등하다',
  '오늘 득템, 내일 풍요',
  '사지 않으면 100% 할인, 잘 사면 200% 만족',
  '지갑이 얇을수록 눈이 높아진다',
]

function getKstDayIndex() {
  const now = new Date()
  const kstDate = new Date(now.getTime() + 9 * 60 * 60 * 1000)
  return Math.floor(kstDate.getTime() / (1000 * 60 * 60 * 24))
}

export function getDailyPhrase(offset = 0) {
  return PHRASES[(getKstDayIndex() + offset) % PHRASES.length]
}

export function getMsUntilKstMidnight() {
  const now = new Date()
  const kstNow = new Date(now.getTime() + 9 * 60 * 60 * 1000)
  return (
    24 * 60 * 60 * 1000 -
    ((kstNow.getUTCHours() * 60 + kstNow.getUTCMinutes()) * 60 +
      kstNow.getUTCSeconds()) *
      1000
  )
}
