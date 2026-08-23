# grammar_report.py -- verbatim 53-production CFG + rule set from lean_experiments.py (Section 1), for post-hoc scoring consistency.

GRAMMAR = r"""
    start: tactic

    tactic: rw_tac
          | simp_tac
          | exact_tac
          | apply_tac
          | refine_tac
          | have_tac
          | obtain_tac
          | rintro_tac
          | intro_tac
          | ext_tac
          | rfl_tac
          | induction_tac
          | cases_tac
          | by_cases_tac
          | calc_tac
          | classical_tac
          | constructor_tac
          | contrapose_tac
          | suffices_tac
          | focus_tac
          | rcases_tac
          | grind_tac
          | gcongr_tac
          | linarith_tac
          | split_ifs_tac
          | infer_instance_tac
          | aesop_tac
          | by_contra_tac
          | change_tac
          | congr_tac
          | convert_tac
          | positivity_tac
          | all_goals_tac
          | fin_cases_tac
          | case_arm_tac
          | dsimp_tac
          | let_tac
          | lia_tac
          | fun_prop_tac
          | cat_disch_tac
          | use_tac
          | ring_tac
          | filter_upwards_tac
          | norm_cast_tac
          | unfold_tac
          | grw_tac
          | norm_num_tac
          | decide_tac
          | subst_tac
          | cfc_tac_tac
          | tauto_tac
          | finiteness_tac
          | contrapose_bare_tac
          | generic_tac

    case_arm_tac.3: "|" CASE_PATTERN "=>" tactic?
    CASE_PATTERN: /[^=]+?(?=\s*=>)/

    focus_tac.3:       "\u00b7" tactic

    rw_tac.2:          "rw"i ARGS
    simp_tac.2:         SIMP_KW ARGS?
    exact_tac.2:        EXACT_KW ARGS
    apply_tac.2:        "apply"i ARGS
    refine_tac.2:        "refine"i ARGS
    have_tac.2:          "have"i ARGS
    obtain_tac.2:        "obtain"i ARGS
    rintro_tac.2:        "rintro"i ARGS
    intro_tac.2:         "intro"i ARGS?
    ext_tac.2:           EXT_KW ARGS?
    rfl_tac.2:           "rfl"i
    induction_tac.2:     "induction"i ARGS
    cases_tac.2:         "cases"i ARGS
    by_cases_tac.2:      "by_cases"i ARGS
    calc_tac.2:          "calc"i ARGS
    classical_tac.2:     "classical"i
    constructor_tac.2:   "constructor"i
    contrapose_tac.2:    "contrapose!"i ARGS?
    suffices_tac.2:      "suffices"i ARGS
    rcases_tac.2:        "rcases"i ARGS
    grind_tac.2:         "grind"i ARGS?
    gcongr_tac.2:        "gcongr"i ARGS?
    linarith_tac.2:      LINARITH_KW ARGS?
    split_ifs_tac.2:     "split_ifs"i ARGS?
    infer_instance_tac.2:"infer_instance"i
    aesop_tac.2:         AESOP_KW ARGS?
    by_contra_tac.2:     "by_contra"i ARGS?
    change_tac.2:        "change"i ARGS
    congr_tac.2:         "congr"i ARGS?
    convert_tac.2:       CONVERT_KW ARGS
    positivity_tac.2:    "positivity"i
    all_goals_tac.2:     "all_goals"i ARGS
    fin_cases_tac.2:     "fin_cases"i ARGS

    dsimp_tac.2:         "dsimp"i ARGS?
    let_tac.2:           "let"i ARGS
    lia_tac.2:           "lia"i
    fun_prop_tac.2:      "fun_prop"i ARGS?
    cat_disch_tac.2:     "cat_disch"i
    use_tac.2:           "use"i ARGS
    ring_tac.2:          RING_KW
    filter_upwards_tac.2:"filter_upwards"i ARGS?
    norm_cast_tac.2:     NORM_CAST_KW ARGS?
    unfold_tac.2:        "unfold"i ARGS
    grw_tac.2:           "grw"i ARGS
    norm_num_tac.2:      "norm_num"i ARGS?
    decide_tac.2:        "decide"i
    subst_tac.2:         "subst"i ARGS
    cfc_tac_tac.2:       "cfc_tac"i
    tauto_tac.2:         "tauto"i
    finiteness_tac.2:    "finiteness"i
    contrapose_bare_tac.2:"contrapose"i ARGS?

    RING_KW: "ring" | "ring_nf" | "ring1"
    NORM_CAST_KW: "norm_cast" | "push_cast"

    LINARITH_KW: "linarith" | "nlinarith" | "polyrith"
    AESOP_KW: "aesop" | "aesop_graph" | "aesop_cat"
    CONVERT_KW: "convert" | "convert!"

    generic_tac.-1: IDENT ARGS?

    SIMP_KW: "simp" | "simpa" | "simp_all" | "simp_rw" | "nth_rw"
    EXACT_KW: "exact" | "exact_mod_cast" | "rwa"
    EXT_KW: "ext" | "ext1" | "funext"

    IDENT: /[A-Za-z_][A-Za-z0-9_'!]*/
    ARGS: /.+/

    %import common.WS
    %ignore WS
"""


NAMED_RULES = {
    'rw_tac', 'simp_tac', 'exact_tac', 'apply_tac', 'refine_tac', 'have_tac',
    'obtain_tac', 'rintro_tac', 'intro_tac', 'ext_tac', 'rfl_tac',
    'induction_tac', 'cases_tac', 'by_cases_tac', 'calc_tac', 'classical_tac',
    'constructor_tac', 'contrapose_tac', 'suffices_tac', 'focus_tac',
    'rcases_tac', 'grind_tac', 'gcongr_tac', 'linarith_tac', 'split_ifs_tac',
    'infer_instance_tac', 'aesop_tac', 'by_contra_tac', 'change_tac',
    'congr_tac', 'convert_tac', 'positivity_tac', 'all_goals_tac', 'fin_cases_tac',
    'case_arm_tac', 'dsimp_tac', 'let_tac', 'lia_tac', 'fun_prop_tac',
    'cat_disch_tac', 'use_tac', 'ring_tac', 'filter_upwards_tac', 'norm_cast_tac',
    'unfold_tac', 'grw_tac', 'norm_num_tac', 'decide_tac', 'subst_tac',
    'cfc_tac_tac', 'tauto_tac', 'finiteness_tac', 'contrapose_bare_tac',
}
