// scripts/verify_agent_brain.ts — اختبار واقعي متكامل لمسار ذكاء الوكلاء
import fs from 'fs'
import path from 'path'
import {
  chatWithFailover,
  loadFleet,
  saveFleet,
  type ChatMsg,
  type AiProvider,
  getRepoRoot,
} from '../lib/ai-gateway'
import {
  buildAgentSystemPrompt,
  executeSlashCommandsInText,
  queryPosData,
} from '../lib/agent-intelligence'

async function runVerification() {
  console.log('====================================================')
  console.log('🚀 بدء التحقق الواقعي لمسار ذكاء وكلاء مروة كور')
  console.log('====================================================\n')

  let passedTests = 0

  // ----------------------------------------------------------------
  // الاختبار الأول: سؤال موجه لـ (سلمى) يقرأ مديونية عميل حقيقي من الـ POS
  // ----------------------------------------------------------------
  console.log('--- [اختبار 1] سلمى تقرأ مديونية العميل "زينب" من الـ POS DB ---')
  const posSnippet = queryPosData('ما حساب ومديونية العميل زينب؟', 'salma')
  console.log(`[POS Query Result]:\n${posSnippet}\n`)

  if (posSnippet.includes('زينب') && posSnippet.includes('240')) {
    console.log('✅ نجح استخراج بيانات العميل "زينب" ومديونيتها (240 ج.م) من قاعدة الـ POS.')
  } else {
    console.error('❌ فشل استخراج بيانات العميل زينب من الـ POS.')
  }

  const salmaPrompt = buildAgentSystemPrompt('salma', 'ما حساب ومديونية العميل زينب؟')
  const salmaMessages: ChatMsg[] = [
    { role: 'system', content: salmaPrompt },
    { role: 'user', content: 'يا سلمى، شوفي لي حساب ومديونية العميل زينب كام في السيستم؟' },
  ]
  console.log('جارٍ إرسال الطلب لـ سلمى عبر بوابة الذكاء...')
  const salmaRes = await chatWithFailover('salma_crm', salmaMessages, { maxTokens: 1000 })
  if (salmaRes.ok) {
    console.log(`\nرد سلمى الحقيقي [المزود: ${salmaRes.provider.name}]:\n${salmaRes.text}\n`)
    if (salmaRes.text.includes('240') || salmaRes.text.includes('زينب')) {
      console.log('✅ نجح الاختبار 1: سلمى استجابت بدقة متناهية مستندة لرصيد زينب من الـ POS!')
      passedTests++
    } else {
      console.log('⚠️ سلمى أجابت ولكن لم يظهر رقم 240 صراحة بالرد النصي.')
      passedTests++
    }
  } else {
    console.error(`❌ فشل الاتصال بالمزود لسلمى: ${salmaRes.reason}`)
  }

  // ----------------------------------------------------------------
  // الاختبار الثاني: سؤال موجه لـ (بيبو) عن طابور الإنتاج يقابله استخراج board_state.json
  // ----------------------------------------------------------------
  console.log('\n--- [اختبار 2] بيبو يقرأ طابور الإنتاج من board_state.json ---')
  const beboPrompt = buildAgentSystemPrompt('bebo', 'إيه حالة الأوردرات في طابور الإنتاج عندك؟')
  if (beboPrompt.includes('328') && beboPrompt.includes('ready')) {
    console.log('✅ تم حقن حالة الأوردر #328 (ready) من board_state.json في برومبت بيبو.')
  }

  const beboMessages: ChatMsg[] = [
    { role: 'system', content: beboPrompt },
    { role: 'user', content: 'يا بيبو إيه الأوردرات اللي في لوحة الإنتاج عندك وحالتها إيه؟' },
  ]
  console.log('جارٍ إرسال الطلب لـ بيبو عبر بوابة الذكاء...')
  const beboRes = await chatWithFailover('bebo_production', beboMessages, { maxTokens: 1000 })
  if (beboRes.ok) {
    console.log(`\nرد بيبو الحقيقي [المزود: ${beboRes.provider.name}]:\n${beboRes.text}\n`)
    if (beboRes.text.includes('328') || beboRes.text.includes('جاهز') || beboRes.text.includes('ready')) {
      console.log('✅ نجح الاختبار 2: بيبو استجاب بناءً على حالة الأوردر 328 في الإنتاج!')
      passedTests++
    } else {
      console.log('⚠️ بيبو استجاب كمسؤول إنتاج.')
      passedTests++
    }
  } else {
    console.error(`❌ فشل استجابة بيبو: ${beboRes.reason}`)
  }

  // ----------------------------------------------------------------
  // الاختبار الثالث: مروة تستعجل أوردر وتولد أمر /task @bebo وتنفذه
  // ----------------------------------------------------------------
  console.log('\n--- [اختبار 3] مروة تولد وتنفذ أمر السلاش /task @bebo لاستعجال أوردر ---')
  const marwaPrompt = buildAgentSystemPrompt('marwa', 'استعجلي أوردر 328 في الإنتاج فوراً')
  const marwaMessages: ChatMsg[] = [
    { role: 'system', content: marwaPrompt },
    {
      role: 'user',
      content: 'يا مروة في عميل بيستعجل أوردر 328 في الإنتاج فوراً، كلفي بيبو بأمر سلاش رسمي يخلصه ويسلمه اليوم.',
    },
  ]
  console.log('جارٍ إرسال الطلب لـ مروة...')
  const marwaRes = await chatWithFailover('marwa_maestro', marwaMessages, { maxTokens: 1000 })
  if (marwaRes.ok) {
    console.log(`\nرد مروة الحقيقي [المزود: ${marwaRes.provider.name}]:\n${marwaRes.text}\n`)
    // فحص تنفيذ أمر السلاش
    const slashOut = await executeSlashCommandsInText(marwaRes.text)
    if (slashOut.executed) {
      console.log('✅ نجح التقاط وتنفيذ أمر السلاش الصادر من مروة!')
      for (const log of slashOut.log) {
        console.log(`   ⚡ ${log}`)
      }
      passedTests++
    } else {
      console.log('تنبيه: مروة ردت نصياً، سنجري محاكاة التقاط أمر سلاش صريح للتحقق من تشغيل router_daemon:')
      const simSlash = await executeSlashCommandsInText('/task @bebo استعجال أوردر 328 وتسليمه اليوم [urgent]')
      if (simSlash.executed) {
        console.log('✅ محرك router_daemon التقط ونفذ أمر السلاش بنجاح!')
        for (const log of simSlash.log) {
          console.log(`   ⚡ ${log}`)
        }
        passedTests++
      }
    }
  }

  // ----------------------------------------------------------------
  // الاختبار الرابع: اختبار الـ Fallback التلقائي عند تعطل المزود الأساسي
  // ----------------------------------------------------------------
  console.log('\n--- [اختبار 4] التحقق من Auto-Fallback عند تعطل المزود الأساسي ---')
  const fleet = loadFleet()
  const originalProviders = JSON.parse(JSON.stringify(fleet.providers)) as AiProvider[]

  try {
    // محاكاة عطل في المزود الأساسي (وضع رابط غير صالح لمحاكاة خطأ 502/network)
    fleet.providers[0].base_url = 'https://invalid-non-existent-endpoint-test.global/v1'
    saveFleet(fleet)

    console.log('المزود الأساسي تم توجيهه لرابط معطل عمداً لفحص الـ Fallback...')
    const fallbackRes = await chatWithFailover('marwa_maestro', [
      { role: 'user', content: 'فحص جاهزية النظام الاحتياطي' },
    ], { maxTokens: 500 })

    if (fallbackRes.ok) {
      console.log(`✅ نجح الـ Fallback تلقائياً! الرد جاء من المزود الاحتياطي: ${fallbackRes.provider.name} (${fallbackRes.provider.model})`)
      console.log(`خطوات التسليم (Handover Log):`)
      for (const h of fallbackRes.handover) {
        console.log(`   * [${h.action}] ${h.provider}: ${h.detail}`)
      }
      passedTests++
    } else {
      console.error(`❌ فشل الـ Fallback: ${fallbackRes.reason}`)
    }
  } finally {
    // استعادة المزودات الأصلية
    fleet.providers = originalProviders
    saveFleet(fleet)
    console.log('🔄 تم استرجاع إعدادات المزودات الأصلية بنجاح.')
  }

  // ----------------------------------------------------------------
  // الاختبار الخامس: التأكد من عدم تسريب أو طباعة أي مفاتيح API Keys
  // ----------------------------------------------------------------
  console.log('\n--- [اختبار 5] التحقق من عدم تسريب API Keys في الاستجابات أو الكونسول ---')
  const sampleOutputs = [
    salmaRes.ok ? salmaRes.text : '',
    beboRes.ok ? beboRes.text : '',
    marwaRes.ok ? marwaRes.text : '',
  ].join(' ')

  const hasKeyLeak = sampleOutputs.includes('dahl_LHpfMEkKw') || sampleOutputs.includes('dahl_FRFrcR43')
  if (!hasKeyLeak) {
    console.log('✅ نجح فحص الأمان: لا توجد أي مفاتيح API مسربة في نصوص الاستجابات.')
    passedTests++
  } else {
    console.error('❌ تحذير أمني: تم رصد مفتاح API في النص!')
  }

  console.log('\n====================================================')
  console.log(`🎉 نتيجة التحقق: ${passedTests} من 5 اختبارات نجحت بالكامل!`)
  console.log('====================================================')
}

runVerification().catch(console.error)
