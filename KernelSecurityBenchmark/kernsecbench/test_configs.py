BASE_DEFCONFIG = "manmin_nosec_defconfig"


# mitigations=off is equivalent to:
#  off
# Disable all optional CPU mitigations.  This
# improves system performance, but it may also
# expose users to several CPU vulnerabilities.
# Equivalent to: gather_data_sampling=off [X86]
#                kvm.nx_huge_pages=off [X86]
#                l1tf=off [X86]
#                mds=off [X86]
#                mmio_stale_data=off [X86]
#                nopti [X86,PPC]
#                nospectre_v1 [X86,PPC]
#                nospectre_v2 [X86,PPC,S390,ARM64]
#                reg_file_data_sampling=off [X86]
#                retbleed=off [X86]
#                spec_rstack_overflow=off [X86]
#                spec_store_bypass_disable=off [X86,PPC]
#                spectre_bhi=off [X86]
#                spectre_v2_user=off [X86]
#                srbds=off [X86,INTEL]
#                tsx_async_abort=off [X86]



# Adding entries to this map will automatically be incorperating into test and analysis
BASE_MIT_OPTIONS = "nospectre_bhb nospectre_v1 spectre_v2=off spectre_v2_user=off retbleed=off pti=off spec_rstack_overflow=off"
kconfig_map = {
    # Disable all mitigations (see the effect of 'all other configs')
    "all_mit_off": ("", "mitigations=off"),
    
    # Baseline config, disable mitigations we test for 
    "basline": ("", BASE_MIT_OPTIONS),
    # BASE_MIT_OPTIONS =                                                "nospectre_v1 spectre_v2=off spectre_v2_user=off retbleed=off pti=off spec_rstack_overflow=off"

    # Various spectre_v2 mitigations
    "retpoline_generic": ("CONFIG_RETPOLINE=y",                         "nospectre_v1 spectre_v2=retpoline,generic spectre_v2_user=off retbleed=off pti=off spec_rstack_overflow=off"),
    "ibrs": ("CONFIG_CPU_IBRS_ENTRY=y",                                 "nospectre_v1 spectre_v2=ibrs spectre_v2_user=off retbleed=off pti=off spec_rstack_overflow=off"),
    "eibrs": ("CONFIG_CPU_IBRS_ENTRY=y",                                "nospectre_v1 spectre_v2=eibrs, spectre_v2_user=off retbleed=off pti=off spec_rstack_overflow=off"),
 #   "retpoline_eibrs": ("CONFIG_RETPOLINE=y\nCONFIG_CPU_IBRS_ENTRY=y",  "nospectre_v1 spectre_v2=eibrs,retpoline,generic spectre_v2_user=off retbleed=off pti=off"),
 #   "retpoline_ibrs": ("CONFIG_RETPOLINE=y\nCONFIG_CPU_IBRS_ENTRY=y",   "nospectre_v1 spectre_v2=ibrs,retpoline,generic spectre_v2_user=off retbleed=off pti=off"),
    "all_spectre_v2": ("CONFIG_RETPOLINE=y\nCONFIG_CPU_IBRS_ENTRY=y",   "nospectre_v1 spectre_v2=ibrs,eibrs,retpoline,generic spectre_v2_user=off retbleed=off pti=off spec_rstack_overflow=off"),
    "on_spectre_v2": ("CONFIG_RETPOLINE=y\nCONFIG_CPU_IBRS_ENTRY=y",    "nospectre_v1 spectre_v2=on spectre_v2_user=on retbleed=off pti=off spec_rstack_overflow=off"),

    # # With spectre_v1 mitigations
    # "spectre_v1": ("CONFIG_RETPOLINE=y",                                "spectre_v2=off spectre_v2_user=off retbleed=off pti=off"),

    "pti_on": ("CONFIG_PAGE_TABLE_ISOLATION=y",                         "nospectre_v1 spectre_v2=off spectre_v2_user=off retbleed=off pti=on spec_rstack_overflow=off"),


    "ibpb_on": ("CONFIG_CPU_IBPB_ENTRY=y",                              "nospectre_v1 spectre_v2=off spectre_v2_user=off retbleed=ibpb pti=off spec_rstack_overflow=ibpb"),
    
    "page_poisoning": ("CONFIG_PAGE_POISONING=y", BASE_MIT_OPTIONS + " page_poison=1"),
    "memory_leak_detector": ("CONFIG_DEBUG_KMEMLEAK=y", BASE_MIT_OPTIONS),
    "kernel_address_sanitizer": ("CONFIG_KASAN=y", BASE_MIT_OPTIONS),
    "init_on_free_alloc": ("CONFIG_INIT_ON_FREE_DEFAULT_ON=y\nCONFIG_INIT_ON_ALLOC_DEFAULT_ON=y", BASE_MIT_OPTIONS + " init_on_free=1 init_on_alloc=1"),
    "hardened_usercopy": ("CONFIG_HARDENED_USERCOPY=y", BASE_MIT_OPTIONS),
    "randstruct_full": ("CONFIG_RANDSTRUCT_FULL=y", BASE_MIT_OPTIONS),
    "debug_pagealloc": ("CONFIG_DEBUG_PAGEALLOC=y\nCONFIG_DEBUG_PAGEALLOC_ENABLE_DEFAULT=y", BASE_MIT_OPTIONS),
  #  "slab_freelist_random": ("CONFIG_SLAB_FREELIST_RANDOM=y", BASE_MIT_OPTIONS),
  #  "random_kmalloc_caches": ("CONFIG_RANDOM_KMALLOC_CACHES=y", BASE_MIT_OPTIONS),
}
