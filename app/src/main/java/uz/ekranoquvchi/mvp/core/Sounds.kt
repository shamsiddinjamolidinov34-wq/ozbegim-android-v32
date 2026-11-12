package uz.ekranoquvchi.mvp.core

import android.content.Context
import uz.ekranoquvchi.mvp.R
import uz.ekranoquvchi.mvp.util.Prefs

/**
 * Tovush signallari katalogi (v32). Har bir tovush res/raw dagi bitta WAV fayl: ularning hammasi tools/make_sounds.py
 * skripti bilan matematik usulda yaratilgan (tashqi yozuv ishlatilmagan, shuning uchun mualliflik huquqi muammosi yo'q).
 *
 * "Mavzu" har bir hodisa (fokus, bosish, chegara, oyna, surish, xato) uchun tayyor tovushlar to'plami. Foydalanuvchi
 * istasa, har bir hodisaga katalogdan alohida tovush tanlaydi yoki uni o'chiradi (Prefs.earconOverride).
 */
object Sounds {
    /** Tovushlar guruhi: sozlamalardagi "Tinglab ko'rish" ro'yxatida sarlavha bo'ladi. */
    enum class Group(val titleRes: Int) {
        TONE(R.string.snd_group_tone),
        WATER(R.string.snd_group_water),
        RAIN(R.string.snd_group_rain),
        NATURE(R.string.snd_group_nature),
        ZEN(R.string.snd_group_zen),
    }

    /**
     * @param id kalit (saqlanadigan qiymat; res/raw/snd_<id>.wav fayl nomi bilan bir xil)
     * @param nature true bo'lsa har ijroda tezlik biroz o'zgartiriladi (tabiatda ikki tovush bir xil emas, takrorlanish zerikarli bo'lmaydi)
     */
    class Sound(val id: String, val raw: Int, val nameRes: Int, val group: Group, val nature: Boolean)

    val ALL: List<Sound> = listOf(
        Sound("tone_tik", R.raw.snd_tone_tik, R.string.snd_name_tone_tik, Group.TONE, false),
        Sound("tone_tuk", R.raw.snd_tone_tuk, R.string.snd_name_tone_tuk, Group.TONE, false),
        Sound("tone_edge", R.raw.snd_tone_edge, R.string.snd_name_tone_edge, Group.TONE, false),
        Sound("tone_window", R.raw.snd_tone_window, R.string.snd_name_tone_window, Group.TONE, false),
        Sound("tone_scroll", R.raw.snd_tone_scroll, R.string.snd_name_tone_scroll, Group.TONE, false),
        Sound("tone_error", R.raw.snd_tone_error, R.string.snd_name_tone_error, Group.TONE, false),

        Sound("drop_tiny", R.raw.snd_drop_tiny, R.string.snd_name_drop_tiny, Group.WATER, true),
        Sound("drop_water", R.raw.snd_drop_water, R.string.snd_name_drop_water, Group.WATER, true),
        Sound("drop_deep", R.raw.snd_drop_deep, R.string.snd_name_drop_deep, Group.WATER, true),
        Sound("drop_pair", R.raw.snd_drop_pair, R.string.snd_name_drop_pair, Group.WATER, true),
        Sound("water_splash", R.raw.snd_water_splash, R.string.snd_name_water_splash, Group.WATER, true),
        Sound("water_ripple", R.raw.snd_water_ripple, R.string.snd_name_water_ripple, Group.WATER, true),
        Sound("water_brook", R.raw.snd_water_brook, R.string.snd_name_water_brook, Group.WATER, true),
        Sound("water_wave", R.raw.snd_water_wave, R.string.snd_name_water_wave, Group.WATER, true),

        Sound("rain_tap", R.raw.snd_rain_tap, R.string.snd_name_rain_tap, Group.RAIN, true),
        Sound("rain_leaves", R.raw.snd_rain_leaves, R.string.snd_name_rain_leaves, Group.RAIN, true),
        Sound("rain_shower", R.raw.snd_rain_shower, R.string.snd_name_rain_shower, Group.RAIN, true),

        Sound("bird_tweet", R.raw.snd_bird_tweet, R.string.snd_name_bird_tweet, Group.NATURE, true),
        Sound("bird_trill", R.raw.snd_bird_trill, R.string.snd_name_bird_trill, Group.NATURE, true),
        Sound("bird_dove", R.raw.snd_bird_dove, R.string.snd_name_bird_dove, Group.NATURE, true),
        Sound("cricket", R.raw.snd_cricket, R.string.snd_name_cricket, Group.NATURE, true),
        Sound("leaf_rustle", R.raw.snd_leaf_rustle, R.string.snd_name_leaf_rustle, Group.NATURE, true),
        Sound("wind_breeze", R.raw.snd_wind_breeze, R.string.snd_name_wind_breeze, Group.NATURE, true),

        Sound("bamboo_tap", R.raw.snd_bamboo_tap, R.string.snd_name_bamboo_tap, Group.ZEN, true),
        Sound("wood_block", R.raw.snd_wood_block, R.string.snd_name_wood_block, Group.ZEN, true),
        Sound("pebble", R.raw.snd_pebble, R.string.snd_name_pebble, Group.ZEN, true),
        // Ohangli tovushlar (qo'ng'iroq, kosa): balandligi o'zgarsa kuy buziladi, shuning uchun har safar bir xil
        Sound("chime_wind", R.raw.snd_chime_wind, R.string.snd_name_chime_wind, Group.ZEN, false),
        Sound("bowl_soft", R.raw.snd_bowl_soft, R.string.snd_name_bowl_soft, Group.ZEN, false),
    )

    private val BY_ID: Map<String, Sound> = ALL.associateBy { it.id }

    fun byId(id: String?): Sound? = if (id == null) null else BY_ID[id]

    // ------------------------------------------------------------------ mavzular

    /** Mavzu: har bir hodisa uchun bitta tovush (id lar ALL ro'yxatidagi bilan bir xil). */
    class Theme(
        val id: String,
        val nameRes: Int,
        val focus: String,
        val click: String,
        val edge: String,
        val window: String,
        val scroll: String,
        val error: String,
    ) {
        fun soundId(kind: Earcons.Kind): String = when (kind) {
            Earcons.Kind.FOCUS -> focus
            Earcons.Kind.CLICK -> click
            Earcons.Kind.EDGE -> edge
            Earcons.Kind.WINDOW -> window
            Earcons.Kind.SCROLL -> scroll
            Earcons.Kind.ERROR -> error
        }
    }

    /** Standart mavzu v31 dagi to'rtta ohangni aynan saqlaydi (fokus, bosish, chegara, oyna), shuning uchun yangilanishda hech narsa o'zgarmaydi. */
    const val DEFAULT_THEME = "classic"

    val THEMES: List<Theme> = listOf(
        Theme("classic", R.string.snd_theme_classic, "tone_tik", "tone_tuk", "tone_edge", "tone_window", "tone_scroll", "tone_error"),
        Theme("water", R.string.snd_theme_water, "drop_tiny", "drop_water", "water_ripple", "water_wave", "drop_pair", "drop_deep"),
        Theme("rain", R.string.snd_theme_rain, "rain_tap", "rain_leaves", "wind_breeze", "rain_shower", "leaf_rustle", "drop_deep"),
        Theme("forest", R.string.snd_theme_forest, "wood_block", "bird_tweet", "bird_dove", "bird_trill", "cricket", "bamboo_tap"),
        Theme("zen", R.string.snd_theme_zen, "pebble", "bamboo_tap", "bowl_soft", "chime_wind", "wood_block", "drop_deep"),
        Theme("mix", R.string.snd_theme_mix, "drop_tiny", "bamboo_tap", "bird_dove", "chime_wind", "leaf_rustle", "drop_deep"),
    )

    private val THEME_BY_ID: Map<String, Theme> = THEMES.associateBy { it.id }

    val THEME_IDS: Set<String> = THEMES.map { it.id }.toSet()

    fun theme(id: String?): Theme = THEME_BY_ID[id] ?: THEME_BY_ID.getValue(DEFAULT_THEME)

    // ------------------------------------------------------------------ har bir hodisaga alohida tanlov

    /** Hodisa tovushi mavzudagidek bo'ladi (standart). */
    const val OVERRIDE_THEME = "theme"

    /** Hodisa tovushi o'chiq: boshqa hodisalar eshitilaveradi. */
    const val OVERRIDE_OFF = "off"

    /** Hodisa uchun saqlanadigan qiymatlar: "theme", "off" yoki katalogdagi tovush id si (zaxira nusxani tekshirishda ham ishlatiladi). */
    val OVERRIDE_VALUES: Set<String> = linkedSetOf(OVERRIDE_THEME, OVERRIDE_OFF) + ALL.map { it.id }

    /** Hodisaning sozlamalardagi nomi. */
    fun eventTitleRes(kind: Earcons.Kind): Int = when (kind) {
        Earcons.Kind.FOCUS -> R.string.snd_event_focus
        Earcons.Kind.CLICK -> R.string.snd_event_click
        Earcons.Kind.EDGE -> R.string.snd_event_edge
        Earcons.Kind.WINDOW -> R.string.snd_event_window
        Earcons.Kind.SCROLL -> R.string.snd_event_scroll
        Earcons.Kind.ERROR -> R.string.snd_event_error
    }

    /** Hodisa uchun hozir ijro etiladigan tovush; null bo'lsa shu hodisa o'chirilgan (yoki saqlangan qiymat noma'lum). */
    fun resolve(context: Context, kind: Earcons.Kind): Sound? {
        val over = Prefs.earconOverride(context, kind)
        if (over == OVERRIDE_OFF) return null
        if (over != OVERRIDE_THEME) {
            val own = BY_ID[over]
            if (own != null) return own
        }
        return BY_ID[theme(Prefs.earconTheme(context)).soundId(kind)]
    }
}
