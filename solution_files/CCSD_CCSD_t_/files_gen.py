import os
import uuid
import json
import datetime
from pathlib import Path

##############################################################
# 1. Folders to store CCSD and CCSD(T) solutions
##############################################################
CCSD_SOLUTIONS_FOLDER = Path("ccsd_solutions")
CCSDT_SOLUTIONS_FOLDER = Path("ccsdt_solutions")
CCSD_SOLUTIONS_FOLDER.mkdir(exist_ok=True)
CCSDT_SOLUTIONS_FOLDER.mkdir(exist_ok=True)

##############################################################
# 2. Define exactly one solver UUID for CCSD and one for CCSD(T)
#    Then reuse these across all solutions.
##############################################################
CCSD_SOLVER_UUID = "77bb1af4-9091-4788-9b73-6bf34b3ec426"    # Example: set once for CCSD
CCSDT_SOLVER_UUID = "e534a7c2-00a9-4587-b0c2-9d2a6af08340"   # Example: set once for CCSD(T)

# Define solver details with these fixed solver UUIDs
CCSD_SOLVER_DETAILS = {
    "solver_uuid": CCSD_SOLVER_UUID,
    "solver_short_name": "CCSD",
    "compute_hardware_type": "classical_computer",
    "classical_hardware_details": {
        "computing_environment_name": "Local Desktop",
        "cpu_description": "Intel(R) Core(TM) i5-7500 CPU @ 3.40GHz",
        "ram_available_gb": 7.6,
        "clock_speed": "3.4 GHz",
        "total_num_cores": 4
    },
    "algorithm_details": {
        "description": "Coupled Cluster Singles and Doubles"
    },
    "software_details": {
        "description": "PySCF 2.8.0"
    }
}

CCSDT_SOLVER_DETAILS = {
    "solver_uuid": CCSDT_SOLVER_UUID,
    "solver_short_name": "CCSD(T)",
    "compute_hardware_type": "classical_computer",
    "classical_hardware_details": {
        "computing_environment_name": "Local Desktop",
        "cpu_description": "Intel(R) Core(TM) i5-7500 CPU @ 3.40GHz",
        "ram_available_gb": 7.6,
        "clock_speed": "3.4 GHz",
        "total_num_cores": 4
    },
    "algorithm_details": {
        "description": "Coupled Cluster Singles, Doubles, and perturbative Triples [CCSD(T)]"
    },
    "software_details": {
        "description": "PySCF 2.8.0"
    }
}

##############################################################
# 3. Sample CSV-like data 
#    (Truncated here for brevity; place your full lines.)
##############################################################
RAW_DATA = """\
fcidump.0_ru_macho_noncan_0.2_new.46aea10c-d57f-4133-9837-3c57d474d9a2,-2021.1753111636,0.1878,-2021.1755435065,0.0350,Yes
fcidump.10_fecp2+_s0.5_noncan_0.2_new.e10bd99a-435c-41cd-84f1-41bd67890fc7,-1647.0322138976,443.4533,-1647.0487720044,8.0243,No
fcidump.11_fecp2_s0_noncan_0.2_new.b71baf3c-d5f0-4f8d-aead-648ba69a058e,-1647.3341865320,13.4925,-1647.3483290482,1.5251,Yes
fcidump.12_mo_n2_noncan_0.2_new.77c12db8-c32e-4f88-8552-9762a0fff763,-4800.6184520632,14.6104,-4800.6234617292,0.6079,Yes
fcidump.13_1_lut_ts_noncan_0.2_new.09c3ddd5-0187-46e8-95c3-157c470cb69a,-4270.0467809176,34.2835,-4270.0765776708,27.1642,Yes
fcidump.14_1_lut_prod_noncan_0.2_new.f36a9dbc-c34a-401f-8ea6-dc996d785edf,-4270.0935835735,37.1591,-4270.1215371176,31.4016,Yes
fcidump.15_1_lut_react_noncan_0.2_new.9cba211b-820c-4ad4-a050-336e8049e1c7,-4270.0543101136,29.9479,-4270.0869908124,26.2770,Yes
fcidump.16_ts_1over4a_noncan_0.2_new.4476d0ff-9618-4774-9619-e3f223249cea,-2928.3002573479,719.7401,-2928.3186778891,29.7364,No
fcidump.17_ts_1over4a_noncan_0.2_new.d74d0c01-8507-445b-bec1-f02bafbbfaab,-2928.6131716023,173.6821,-2928.6295045595,158.6984,Yes
fcidump.18_I_noncan_0.2_new.f6516937-6182-4dae-a39c-f94c0d72bf70,-2928.4562157626,80.7341,-2928.4716944725,24.1151,Yes
fcidump.19_I_noncan_0.2_new.53abfc75-37a3-440c-a023-6e4cbffecd6a,-2928.5035112609,192.1401,-2928.5204351011,142.2010,Yes
fcidump.1_ru_macho_noncan_0.2_new.496aaf89-2cdf-43cf-8b25-246e915cc8b5,-2021.3453873993,4.5315,-2021.3559388334,0.6595,Yes
fcidump.20_rc_noncan_0.2_new.3527a125-6e74-4df9-a9ac-ebba7d8b84ff,-2928.2591151537,4.2373,-2928.2692842183,0.3455,Yes
fcidump.21_rc_noncan_0.2_new.7fc6d81a-8e1c-436f-ade2-93aed1dfee42,-2928.2920065449,8.4944,-2928.3030583260,1.5300,Yes
fcidump.22_pc-_noncan_0.2_new.2e1dab84-5b1a-4521-8d36-78117ab88bbd,ERROR,Singular matrix,ERROR,ERROR,ERROR
fcidump.23_pc-_noncan_0.2_new.21b0efe8-adc7-44c2-ac49-671cc4b4a1ee,-2928.3354077911,1628.9114,-2928.3554848370,126.7945,No
fcidump.24_ts_1over2_noncan_0.2_new.b96f67e6-fafe-4ccd-ac6f-67afb52f3835,-2928.2006495812,4.0885,-2928.2117484560,0.3724,Yes
fcidump.25_ts_1over2_noncan_0.2_new.47f67a0f-a385-405d-9ac6-2e22f8ceb8e4,ERROR,Singular matrix,ERROR,ERROR,ERROR
fcidump.26_pc_noncan_0.2_new.bed1771c-394c-44e6-93e3-ca41732326d2,-2928.2668808344,5.0234,-2928.2794575721,0.3840,Yes
fcidump.27_pc_noncan_0.2_new.98016425-092d-41a4-b397-9b4b237c582a,ERROR,Singular matrix,ERROR,ERROR,ERROR
fcidump.28_2_noncan_0.2_new.e03635b0-a537-4a58-9f3e-c7114715e47d,ERROR,Singular matrix,ERROR,ERROR,ERROR
fcidump.29_2_noncan_0.2_new.f7797f63-30ab-40e0-8ca6-042c9aa932b4,-2911.2132640386,141.3128,-2911.2132640386,1.4762,No
fcidump.2_co2_0.2_old.1dc29784-ab7f-45a1-9821-31fea4363d74,-187.7211070403,0.1699,-187.7213223897,0.0100,Yes
fcidump.30_4a_noncan_0.2_new.e701d53e-63fe-47f1-b727-39457c9207e6,-2623.0929844880,6.5385,-2623.0980648863,0.3725,Yes
fcidump.31_4a_noncan_0.2_new.21abd0b3-b2cb-4a8a-812e-a8706542f429,-2623.1605321095,15.0036,-2623.1659577571,1.8156,Yes
fcidump.32_2ru_III_3pl_noncan_0.2_new.cb60079d-5a30-4e3a-89d5-dbe95822df5e,-1722.8865750485,0.5241,-1722.8868506156,0.0195,Yes
fcidump.33_2ru_III_3pl_noncan_0.2_new.4811297e-a8df-4150-9d4d-376fd0c6e9cd,-1722.8415575784,153.1002,-1722.8503736864,0.6704,No
fcidump.34_3ruo_IV_2pl_noncan_0.2_new.30c3e4f9-1b24-4fe5-9cab-ad0b67e0d74b,-1796.8034556504,0.7748,-1796.8039348095,0.0201,Yes
fcidump.35_3ruo_IV_2pl_noncan_0.2_new.a2417602-4e97-4395-b3f0-1e29262c8053,-1797.3504588259,19.2965,-1797.3675735759,0.7283,Yes
fcidump.36_1ru_II_2pl_noncan_0.2_new.51f7d629-9a0e-4688-8562-59a5f0c0a404,-1723.4552120425,0.2366,-1723.4553193710,0.0108,Yes
fcidump.37_1ru_II_2pl_noncan_0.2_new.7be1766a-b3f7-4779-9a69-f4358645831b,-1723.5204684527,5.0368,-1723.5219988506,0.5526,Yes
fcidump.38_1_ts_noncan_0.2_new.46967cfc-d867-40e8-bef0-9655c46cef29,-2453.3369608780,3.7984,-2453.3384757449,0.0286,Yes
fcidump.39_1_ts_noncan_0.2_new.85d9d818-501e-4a0e-8fd8-c216ab5e3cb5,-2453.7161938011,1.7645,-2453.7199171687,0.0548,Yes
fcidump.3_ts_ru_macho_co2_noncan_0.2_new.0d7e4a74-fd11-46e3-ba22-044a7ebc54c7,-2208.9810900270,0.4906,-2208.9901180068,0.0490,Yes
fcidump.40_1_ts_noncan_0.2_new.7db0f859-073f-46af-9325-016a67229a4b,-2454.4406513227,41.7645,-2454.4652391674,0.5610,Yes
fcidump.41_1_ts_noncan_0.2_new.2f0b6ced-7831-4fe0-b95e-ce4d456c9c6b,-2454.4876096215,30.5213,-2454.5037335543,0.7914,Yes
fcidump.42_1_star_noncan_0.2_new.a722dd32-93c7-4fbd-9cf5-f1bf44b2cdae,-2452.6679656441,2.2935,-2452.6684715488,0.0303,Yes
fcidump.43_1_star_noncan_0.2_new.d9707874-28d5-48b6-824e-a2e6c8753437,-2452.7512307968,10.8858,-2452.8009825857,0.0921,No
fcidump.44_1_star_noncan_0.2_new.727ab190-e399-4bb6-a9b3-20ae57789bac,ERROR,Singular matrix,ERROR,ERROR,ERROR
fcidump.45_1_star_noncan_0.2_new.e986eb83-6b9d-439e-85ca-a9b931eef4a2,-2454.4761050897,67.1192,-2454.5306772743,0.7020,Yes
fcidump.46_2_noncan_0.2_new.6bf3207c-664b-4ed3-8e74-82b42e277234,-2454.1230469608,10.0667,-2454.1270126151,0.0348,No
fcidump.47_2_noncan_0.2_new.fb3ecfad-6450-423e-aa58-d5cddab6f0f6,ERROR,Singular matrix,ERROR,ERROR,ERROR
fcidump.48_2_noncan_0.2_new.dc406285-bac1-4b99-afbf-06728b7d699b,-2454.5713027588,17.7023,-2454.5940421156,0.6339,Yes
fcidump.49_2_noncan_0.2_new.af9d6a83-7898-4c13-80eb-a83a533ebf2d,-2454.5882480061,73.9184,-2454.6136071961,0.6989,Yes
fcidump.4_ts_ru_macho_co2_noncan_0.2_new.e5e63f77-dbaa-431c-a53f-93c0f4c0758d,-2209.1434763304,7.6011,-2209.1628240350,1.3285,Yes
fcidump.50_6acme_0.2_old.79e71b3e-6364-4972-b4b3-07841fa8ba97,-2592.6846227724,8.0176,-2592.6863197308,0.9583,Yes
fcidump.51_6acme_0.2_old.e8f72c80-2fde-4bdc-ac1e-07220942f1c2,-2592.8096603482,14.7207,-2592.8147868347,3.0835,Yes
fcidump.52_6acme_0.2_old.4854c3ff-b3ce-462b-ab8e-0b132cd880d0,-2592.8675320660,18.8693,-2592.8789694757,6.3726,Yes
fcidump.53_ts56_0.2_old.379a0693-4ac3-4ff0-be33-7be3f6cad84f,-2592.6950988382,9.6035,-2592.7047729384,1.0419,Yes
fcidump.54_ts56_0.2_old.22ab7092-61bb-401f-ac43-912ec10ea48b,-2592.8109728482,14.6956,-2592.8245278481,3.7238,Yes
fcidump.55_ts56_0.2_old.8a8780b0-a0ba-4b7e-9847-589302123e86,-2592.8315497963,16.7123,-2592.8461863349,3.9867,Yes
fcidump.56_5_0.2_old.e6671ea9-f0cf-413c-97cb-c8ab6eda9d5e,-2592.7770281827,8.9250,-2592.7863411706,1.0756,Yes
fcidump.57_5_0.2_old.eb34bf5e-ecd6-4c2a-9eb6-d9bcb507e047,-2592.8769466032,14.4435,-2592.8878989671,3.3863,Yes
fcidump.58_5_0.2_old.5f3178b5-0ad3-469a-ae08-e9ecdc637ed3,-2592.8975574907,14.7301,-2592.9095327842,3.8844,Yes
fcidump.59_5_16_noncan_0.2_new.68af0b80-3d27-4aba-84f9-bcdd30a9255b,-1321.2147291340,18.1246,-1321.2238752584,0.0341,No
fcidump.5_ts_ru_macho_melact_noncan_0.2_new.d7bea809-6e34-49f8-8daf-8d728dd18268,-2402.0379067903,0.4542,-2402.0403887561,0.0400,Yes
fcidump.60_5_16_noncan_0.2_new.28a7820f-63fe-4920-aeec-a7ffe7e55d83,-1321.9952705223,132.4906,-1322.0097722311,0.4086,No
fcidump.61_3_15_af_noncan_0.2_new.f738fcd6-7ddc-4d70-8ff9-4019e3718b04,-1322.5377279311,4.2513,-1322.5652790683,0.0290,Yes
fcidump.62_3_15_af_noncan_0.2_new.6e2bf415-6a69-4b36-ba0f-780a11cb7c0b,-1322.5627979015,126.2759,-1322.5902352882,0.4897,No
fcidump.63_5_15_af_ts_noncan_0.2_new.027490ba-34f9-4340-89ab-27fd110d2821,-1322.5368564907,5.2894,-1322.5444666937,0.0348,Yes
fcidump.64_5_15_af_ts_noncan_0.2_new.bae2da57-6a69-483e-95bc-b77f72ebfba8,-1322.5889050732,146.5154,-1322.6092307770,0.7965,No
fcidump.65_5_15_af_noncan_0.2_new.72343006-774e-4192-b481-fa840ed25573,-1322.4086051387,17.6884,-1322.4161540820,0.0346,No
fcidump.66_5_15_af_noncan_0.2_new.ea55abec-8253-445d-85fa-914948b5e5a5,-1322.5206406326,166.0712,-1322.5351175853,0.6972,No
fcidump.6_ts_ru_macho_melact_noncan_0.2_new.73ae455f-a729-4fac-a626-5654b03c1ef5,-2402.2062805306,7.2689,-2402.2191657598,1.0599,Yes
fcidump.7_melact_0.2_old.5dbed2ac-f9a4-4afe-9b18-f67378a51fb2,-380.8998826102,0.5599,-380.9017438886,0.0284,Yes
fcidump.8_melact_0.2_old.587f69a8-4295-4d6d-811e-0eacfbc5f6dd,-380.8865250478,0.2469,-380.8879431440,0.0932,Yes
fcidump.9_mo_n2-_noncan_0.2_new.23aa47ca-9afe-4086-bd97-75de310e033e,-4800.6371212603,4.1572,-4800.6476691842,0.2561,Yes
fcidump.Cr0_vdz.be2e7f6c-ccba-45ce-a42b-bd1d828b2d18,-86.6043253863,28.4518,-86.6028704404,4.9477,Yes
fcidump.Cr0_vtz.dd44b59c-f6b3-4f9a-acfe-34eaf6de3411,-86.7071802867,66.2289,-86.7206515572,36.6097,Yes
fcidump.Cr1_vdz.69a1826c-1bee-4855-8f5f-5df29035bfca,-86.3665542705,10.4937,-86.3719487696,4.7350,Yes
fcidump.Cr1_vqz.4e3649dd-9050-4acc-93f6-a09c962e89d7,-86.5052509102,218.2791,-86.5184868887,204.9603,Yes
fcidump.Cr1_vtz.efaceb68-6fae-491a-bb90-1e3e3463f010,-86.4615467974,48.3654,-86.4727610119,32.1092,Yes
fcidump.CrO_vdz.b9a18106-c719-4d0c-af12-30ded772eb55,-102.5174230106,100.4542,-102.5534662698,32.5508,Yes
fcidump.Cu0_vdz.48434e2f-f09e-474e-b98c-af180386a258,-197.2223195788,20.0069,-197.2354924688,7.3395,Yes
fcidump.Cu0_vtz.e304b6b5-b820-470d-a8b5-92d6354abd16,-197.4174211425,69.3086,-197.4459850410,56.6508,Yes
fcidump.Cu1_vdz.6facf2d4-6cb3-49b6-8b66-3bd21c1461ec,-196.9574045861,6.4526,-196.9661354264,1.4788,Yes
fcidump.Cu1_vtz.68952c71-d281-40fa-bcd2-cb0352f70a89,-197.1421277701,16.8509,-197.1643580225,8.1131,Yes
fcidump.CuO_vdz.da86aaff-3ca6-4d32-8da2-e1acfe6c31ab,-213.0939832198,117.8667,-213.1162185114,48.1880,Yes
fcidump.Fe0_vdz.133ec573-3d06-4582-b2f5-8afe8be8dbe3,-123.3032999728,242.0247,-123.3143740184,5.8516,No
fcidump.Fe0_vtz.cb274492-6acb-4426-a4f6-8cb4a8cef3c5,-121.9382030854,797.4397,-121.9382030854,43.4601,No
fcidump.Fe1_vdz.b57e3b82-2511-4c00-a850-f6aeba98b0b2,-123.2270986791,16.9848,-123.2331920690,5.6056,Yes
fcidump.Fe1_vtz.b9615d62-11ee-49f7-8df4-df94466b2211,-123.3561592164,50.0337,-123.3685006079,39.5566,Yes
fcidump.FeO_vdz.3f1777dc-c493-4aa7-b3d1-6271d9bed459,-139.1434224467,740.1452,-139.1954167947,41.5301,No
fcidump.Mn0_vdz.a83413fb-96e3-466e-910b-6d4bab7cdf1d,-103.8323435113,268.2147,-103.8418806609,5.3506,No
fcidump.Mn0_vtz.07c9da30-e172-4183-a8af-301628b75f1c,-103.8296147173,771.3284,-103.8407936159,41.0036,No
fcidump.Mn1_vdz.51fac1c9-e29a-4033-b3d3-9cc37f64b4d4,-103.6675480189,10.7336,-103.6731448955,4.9019,Yes
fcidump.Mn1_vtz.00c757c4-3c99-4521-82b1-3e3a12d49854,-103.7814493909,37.9428,-103.7920252668,34.2541,Yes
fcidump.MnO_vdz.55355f72-52f0-427d-b5ac-3b41666ca5fb,-119.8192052427,84.5776,-119.8454937615,35.5915,Yes
fcidump.O0_vdz.c3e26bde-f8e2-4e34-a833-9176dc6c5d58,-15.7790276831,0.7465,-15.7809294976,0.1495,Yes
fcidump.O0_vqz.31ade416-8bd1-4671-953c-c62f281cd96d,-15.8346535861,23.9065,-15.8386603355,11.5897,Yes
fcidump.O0_vtz.1661aaae-621a-430d-990a-bcbbbe270dfb,-15.8230640688,6.2523,-15.8265754618,2.0491,Yes
fcidump.O1_vdz.0767fb16-25bd-4f1c-b134-6b536191b36e,-15.2997699007,1.9304,-15.3005217483,0.3142,Yes
fcidump.O1_vqz.3b587c2c-9579-4c7b-8b3f-e00c69c42981,-15.3397425905,24.3293,-15.3418373008,13.2844,Yes
fcidump.O1_vtz.ee1c9912-bca9-42fa-a90d-421e9a26c785,-15.3315337153,9.0408,-15.3333079999,1.8086,Yes
fcidump.Sc0_vdz.9da0b1fb-c6a5-4da5-b390-3920e3c26154,-46.2756870507,247.2254,-46.2876137398,4.1532,Yes
fcidump.Sc0_vqz.85c6b46a-59fe-4506-89d3-e6faec2383e2,-46.3626905752,1258.1344,-46.3819743955,193.6091,Yes
fcidump.Sc0_vtz.83008296-5ec9-4af7-a03b-372025fad080,-46.3389318863,249.8992,-46.3573282105,27.7187,Yes
fcidump.Sc1_vdz.75228927-fac3-4caf-9e09-1fdfe51098a3,-46.0965119502,162.2694,-46.1037803588,3.8932,No
fcidump.Sc1_vqz.cfc29172-5c9c-4e13-9a31-17895ed89c95,-46.1974417510,298.2755,-46.2081338949,159.8459,Yes
fcidump.Sc1_vtz.adfdddd9-6ebe-4661-8bd8-c8810f117a6a,-46.1746026423,75.8966,-46.1831145181,22.4803,Yes
fcidump.ScO_vdz.987498ce-5b91-4df6-924c-82d4841c17c2,-62.3880408816,48.2763,-62.4172858770,24.6469,Yes
fcidump.Ti0_vdz.cdae3a0c-d613-4375-ab65-7088244b54ef,-57.7768027416,206.9472,-57.7837758182,4.6926,No
fcidump.Ti0_vtz.7766bf7c-05db-4294-b125-6f0110aa9407,-57.8532727191,580.9278,-57.8691874819,30.5493,No
fcidump.Ti1_vdz.760e312c-9982-486d-b50e-d9acb003aedc,-57.6182986945,170.8322,-57.6228076001,4.1996,No
fcidump.Ti1_vtz.2ae865cc-f4c6-4e9f-903c-c8221e06b7a9,-57.6936731659,40.4273,-57.7036015616,26.7173,Yes
fcidump.TiO_vdz.98719f34-8ba8-4557-a9fd-b28a84fe7dd1,-73.8150867706,72.4751,-73.8478080093,27.2434,Yes
fcidump.V0_vdz.950e31e2-142f-480b-b0d1-174381bdb64a,-70.9767433199,231.7444,-70.9866675388,4.8280,No
fcidump.V0_vtz.d85e35e4-fe5c-4ea9-a5aa-d0273321a1dd,-71.0739416019,627.5239,-71.0912003893,32.6709,No
fcidump.V1_vdz.cf7aa422-2b82-4d7c-a031-8923e1fc8a41,-70.8223542809,60.0985,-70.8278374346,4.4512,Yes
fcidump.V1_vtz.1ddf0c08-d7f1-48b7-8c85-c7e50997c771,-70.9083071067,68.5022,-70.9176324591,28.7880,Yes
fcidump.VO_vdz.c6137fbe-c5ef-4572-9e3a-3261e9acaca0,-87.0094144161,81.9652,-87.0440005883,30.1075,Yes
fcidump.be_cc-pVDZ.cc2b3628-dc13-4a95-8765-37211a995068,-14.6173689715,0.2014,-14.6174070488,0.0638,Yes
fcidump.be_cc-pVQZ.f9afcdc1-ce5c-40dd-ae18-0afc933da5bb,-14.6395884515,1.2085,-14.6400832660,0.6226,Yes
fcidump.be_cc-pVTZ.fdc83bd0-c9bd-47da-abee-99b743b36494,-14.6235589041,0.3178,-14.6237901239,0.0633,Yes
fcidump.c2_h2_cc-pVDZ.5b507b3d-b6fc-4e13-9586-06113819d99f,-76.5415701970,7.8379,-76.5850032154,0.6907,Yes
fcidump.c2_h2_cc-pVTZ.57793481-c847-4746-8241-ea949add5f87,-76.5975713263,22.2726,-76.6487318684,6.0811,Yes
fcidump.c2_h4_cc-pVDZ.40035d66-75b8-4b6e-95e5-8b1a3ff1a61d,-77.6009469056,9.3133,-77.6310794637,0.9843,Yes
fcidump.c2_h4_cc-pVTZ.4bd40563-25e1-4334-bf15-3ccd36c05ab2,-77.4360786263,149.1139,-77.5204812025,17.9061,Yes
fcidump.c2_h6_cc-pVDZ.da21513f-c490-45e2-8ce9-1c7a511ca925,-78.6094589610,10.0490,-78.6786073976,1.6874,Yes
fcidump.c_h2_singlet_cc-pVDZ.290cfb48-dbdd-4915-bbaf-b0bc69fa070c,-38.8049741748,0.4636,-38.8181155749,0.0577,Yes
fcidump.c_h2_singlet_cc-pVQZ.7db2ffef-bfc4-4df3-b6a6-c3929e0bb978,-38.7523145695,43.5339,-38.7910603681,9.7048,Yes
fcidump.c_h2_singlet_cc-pVTZ.59fca8b4-25f4-44f7-b961-34d6a4037051,-38.7291995467,9.5861,-38.7713271203,0.9548,Yes
fcidump.c_h3_cl_cc-pVDZ.80298b55-8915-462f-8f20-e4332c94ed41,-498.8891618754,12.4420,-498.9552256106,1.2870,Yes
fcidump.c_h3_cl_cc-pVTZ.a53ae008-4ad2-4736-9a57-cfc011e3aace,-499.0165623787,59.4234,-499.0903053142,30.8665,Yes
fcidump.c_h4_cc-pVDZ.a7321b5d-4730-4ace-9ff8-734ec07f3fef,-39.8430927123,4.8152,-39.8718056789,0.6187,Yes
fcidump.c_h4_cc-pVTZ.47a5eadf-e31e-4c38-983f-8c75460463ea,-39.8817356390,13.6479,-39.9140498168,3.9307,Yes
fcidump.c_o2_cc-pVDZ.b45cfaee-dd16-4f80-963d-ab0f9cc4dab5,-187.5289791273,15.2151,-187.6887134187,0.7940,Yes
fcidump.c_o2_cc-pVTZ.0ffd2489-0b50-49b6-9e6e-7607f14102a9,-187.6671459778,70.4760,-187.9406172529,12.3617,Yes
fcidump.c_o_cc-pVDZ.5de3dbbd-1d79-45c9-ac75-4140ae123baa,-112.5518313700,9.8190,-112.5718972543,0.2342,Yes
fcidump.c_o_cc-pVQZ.0c547725-1536-47b8-98f9-ed1384ceb939,-112.7887021474,50.9118,-112.8965409267,14.7605,Yes
fcidump.c_o_cc-pVTZ.2b749f51-9ea9-41c4-9f67-e9c8334478c4,-112.7328586338,11.5815,-112.8281464491,1.6143,Yes
fcidump.c_s_cc-pVDZ.1c5f7390-3d26-4730-addd-b0fbd7591169,-435.2823100846,16.2736,-435.4004303923,0.4794,Yes
fcidump.c_s_cc-pVTZ.f895f408-4aa7-47e2-a903-c26b963b399e,-435.3754561667,20.7553,-435.4093526053,3.2358,Yes
fcidump.cl2_cc-pVDZ.8d4aaf5e-4bca-4e5b-9fb0-2556228f5c52,-919.1638890037,6.4502,-919.2244273061,0.8183,Yes
fcidump.cl2_cc-pVQZ.7b8c2dbd-8966-4eb4-83af-8acb07454e8a,-919.4463371665,88.9877,-919.5127885426,79.2244,Yes
fcidump.cl2_cc-pVTZ.781d0704-7a95-4183-9c50-cbdbd976884a,-919.3510160324,17.9905,-919.4115652418,7.5067,Yes
fcidump.f2_cc-pVDZ.ac269a87-2bc4-458e-8f4a-64f524c77044,-199.0136795728,5.7381,-199.0779227603,0.2961,Yes
fcidump.f2_cc-pVQZ.29d645f8-ce30-4e18-9f41-644ac5f9d922,-199.2929601181,38.2786,-199.3830101030,18.3274,Yes
fcidump.f2_cc-pVTZ.3c3967d4-17c1-4947-9465-b9223b01e694,-199.2005516941,9.8612,-199.2845826169,1.8467,Yes
fcidump.h2_c_o_cc-pVDZ.d3d8851e-f3df-490c-975a-467933bd9fa1,-113.6517328495,12.7941,-113.6983191246,0.6417,Yes
fcidump.h2_c_o_cc-pVTZ.f1c78add-0e23-423a-bb96-f1370626aa47,-113.7116554936,35.7880,-113.7617685271,5.9881,Yes
fcidump.h2_o2_cc-pVDZ.459b2739-8810-4cd9-82c4-4285c36a0193,-150.8177154298,14.2726,-150.9782550818,0.7388,Yes
fcidump.h2_o2_cc-pVTZ.1a0cce83-5b61-4c4e-a5d4-8825a9b89f65,-150.7829348747,257.9711,-150.8713031160,7.9733,No
fcidump.h2_o_cc-pVDZ.96954db2-ef3e-47fd-82f8-2ac3cbfd6c17,-75.9582325856,0.4865,-75.9762242093,0.0791,Yes
fcidump.h2_o_cc-pVQZ.26e93a92-0fb0-43bf-9c8d-6b97eb974d27,-76.0759933563,32.7692,-76.1027703758,11.6784,Yes
fcidump.h2_o_cc-pVTZ.dd869557-00f9-421f-ab39-faa9d8e05df2,-76.0355434178,6.5672,-76.0600814380,1.1227,Yes
fcidump.h2_s_cc-pVDZ.11a0ff0b-3c6f-416f-be8a-a02acd56aeb9,-398.6173437275,5.4715,-398.6376327125,0.3493,Yes
fcidump.h2_s_cc-pVQZ.57afbbf8-5819-4ee7-b540-95974b8a1a3f,-398.7335619498,51.0608,-398.7638262809,24.9517,Yes
fcidump.h2_s_cc-pVTZ.83f0f242-e184-4581-a77a-f019731d8a6f,-398.6946093562,10.4043,-398.7222157879,2.2365,Yes
fcidump.h3_c_o_h_cc-pVDZ.26a32758-4c43-4add-a12e-7273b2ddfd0e,-114.6943253765,24.6482,-115.0031506316,1.0450,Yes
fcidump.h3_c_o_h_cc-pVTZ.5f3af6fb-63d1-41cf-9e52-ea4fffcca51c,-114.7769714024,115.2185,-115.0937120533,22.9450,Yes
fcidump.h3_c_s_h_cc-pVDZ.65a71ea2-097e-472c-b96a-13ddf6a0962c,-437.3919986986,25.6773,-437.5979311006,1.8707,Yes
fcidump.h_c_n_cc-pVDZ.8ab023ed-7cdf-49e6-87d9-369a13f2ac82,-92.6607568633,8.2934,-92.7743128193,0.5411,Yes
fcidump.h_c_n_cc-pVTZ.6fdfd37c-a5dc-4481-b08e-87dcfec8a4de,-92.7377410138,15.8754,-92.8507642097,3.4461,Yes
fcidump.h_cl_cc-pVDZ.5373214f-f344-4bdb-8840-5acf3b4c07c2,-460.1157365630,0.4971,-460.1258226615,0.0693,Yes
fcidump.h_cl_cc-pVQZ.1235d3d0-2c41-4036-909c-807ed3c89d96,-460.2610409274,16.9926,-460.2809648831,7.8810,Yes
fcidump.h_cl_cc-pVTZ.9ef07114-7e1a-4eba-a9ac-2c71c5fd518a,-460.2110574952,6.5956,-460.2282299636,1.0194,Yes
fcidump.h_f_cc-pVDZ.b93a2eeb-79c3-4f98-8919-f5e0aaedcea7,-100.0687090196,0.3321,-100.0766463503,0.0685,Yes
fcidump.h_f_cc-pVQZ.ff2ff7dd-2eb8-4565-a59e-76a47db07fbc,-100.2261065756,11.4153,-100.2421465684,3.8723,Yes
fcidump.h_f_cc-pVTZ.819ffa8e-51ee-4e78-aa07-17686d7a9488,-100.1748325354,4.3338,-100.1886434017,0.5764,Yes
fcidump.h_o_cl_cc-pVDZ.95dec49b-7d4e-4889-9e31-97e21db7b329,-534.8813762440,18.4920,-534.9641220302,0.7657,Yes
fcidump.h_o_cl_cc-pVTZ.e8ed1ee4-2780-4978-8d21-d1a23a30ae8d,-535.0289164412,271.9503,-537.1671688451,8.6293,No
fcidump.li2_cc-pVDZ.243670ee-2d2e-4d90-abc1-16938a04a80b,-14.8699564305,0.4680,-14.8700867021,0.0662,Yes
fcidump.li2_cc-pVQZ.6224abe8-831e-4b52-b8d9-8ebac0a35c2b,-14.9040090064,26.1200,-14.9053312239,8.0644,Yes
fcidump.li2_cc-pVTZ.26d2547c-96a4-400d-9528-9987ae6699b2,-14.8967185312,6.8597,-14.8976366646,1.0737,Yes
fcidump.li_f_cc-pVDZ.19cf5a4d-e90f-4ab1-a062-b20089724a63,-107.0280514469,0.7550,-107.0318189056,0.0970,Yes
fcidump.li_f_cc-pVQZ.2294b211-7a05-445e-810d-4c1706e1444c,-107.2277933510,33.3836,-107.2386972258,11.7226,Yes
fcidump.li_f_cc-pVTZ.c0df5db1-1bc0-40f5-9cff-6aa2867aba7c,-107.1658641415,8.3068,-107.1743637061,1.4093,Yes
fcidump.li_h_cc-pVDZ.9c6f0876-5690-4391-a98c-0347d111257e,-7.9554736327,0.3050,-7.9554985288,0.0253,Yes
fcidump.li_h_cc-pVQZ.c21d87dd-9338-4498-8ed6-95b0dacd75b1,-7.9787591701,11.9024,-7.9789683866,2.9707,Yes
fcidump.li_h_cc-pVTZ.02d12f52-ff42-4adf-99b9-acada93cb96b,-7.9735430565,1.0178,-7.9736881025,0.4046,Yes
fcidump.n2_cc-pVDZ.60c52c22-d27a-4544-8b9c-6022507611f9,-108.6917289740,9.7755,-108.8568450251,0.2877,Yes
fcidump.n2_cc-pVQZ.e84ef191-bfe0-4859-96b9-0613cad743d4,-109.0206715020,46.2653,-109.1473285346,14.7993,Yes
fcidump.n2_cc-pVTZ.48512c28-04a3-4e3b-b6b2-3e4b654c1887,-108.7906193795,13.3285,-108.8543235955,1.5801,Yes
fcidump.n2_h4_cc-pVDZ.aba33661-3ce8-4f28-824f-e98244906d94,-110.9832681902,14.0127,-111.1524833735,1.0724,Yes
fcidump.n_h3_cc-pVDZ.9820e181-088a-4b00-8a14-8cafb952ccdd,-56.0230126019,0.6182,-56.0543745920,0.0923,Yes
fcidump.n_h3_cc-pVTZ.3b423f54-aa64-4331-a59b-d6c37de1fbb6,-56.0717915093,9.5146,-56.1083001936,2.2327,Yes
fcidump.na2_cc-pVDZ.4ceb8edc-937e-4cb6-9e42-51b6760b2557,-323.7105546093,7.5491,-323.7121032486,0.6465,Yes
fcidump.na2_cc-pVQZ.4d93ba0f-4ad6-4107-b495-9284d226e13d,-323.7426191450,63.7008,-323.7451744613,37.6317,Yes
fcidump.na2_cc-pVTZ.c288da42-cf53-4437-a310-24bf3e35e008,-323.7409190016,14.9881,-323.7430662162,4.4935,Yes
fcidump.na_cl_cc-pVDZ.cd31956d-bef5-4112-9959-510170644e72,-621.4993206850,5.9054,-621.5015604693,0.7053,Yes
fcidump.na_cl_cc-pVQZ.677d97ee-5a46-4d49-82d6-ca3fc98a59a7,-621.6816846383,70.8189,-621.6934573152,56.2298,Yes
fcidump.na_cl_cc-pVTZ.444f3f27-904b-463f-b2f2-c92686c9637d,-621.6238669439,14.4438,-621.6325543348,5.7075,Yes
fcidump.p2_cc-pVDZ.7702bafa-2620-4d12-8ec6-e8c6246d385a,-681.3481898571,96.6867,-681.4014096898,0.8087,No
fcidump.p2_cc-pVQZ.334dbd9d-2c13-4c76-8479-e82280065a02,-681.6542261093,108.2944,-681.7858161928,68.4518,Yes
fcidump.p2_cc-pVTZ.1ffb78a3-162a-43a4-a64c-d1d8fb0bce24,-681.6225439345,24.3824,-681.7604184491,6.6934,Yes
fcidump.p_h3_cc-pVDZ.7ffaab25-7912-4ca9-b0e5-9fe8fd00a0e1,-342.3088725223,6.7685,-342.3398708261,0.6432,Yes
fcidump.p_h3_cc-pVTZ.2b73f8d0-08fe-4cca-9e8a-cda5d21f4761,-342.3709243935,15.8366,-342.4073406663,4.9437,Yes
fcidump.planted_solution_0001.3add17d8-cb86-4ae5-8474-96d272269d80,651.5755338779,0.1009,651.5755338779,0.0239,Yes
fcidump.planted_solution_0002.16f9288f-be7e-4f8a-ab09-0153263f83c7,3045.2147013346,11.3881,3045.2147013346,25.3069,Yes
fcidump.planted_solution_0003.efddd28a-383d-4929-9335-22e54ba2ffbe,-581.5899151298,3.5080,-581.5899151298,0.3220,Yes
fcidump.planted_solution_0004.52ddfe55-8758-448b-a6b1-3afdab85fdf4,-1216.7423221217,2.9186,-1216.7423221217,28.7223,Yes
fcidump.planted_solution_0005.0ddeaaab-a6ef-436b-8189-290afa6408ea,-98.4036218913,0.0357,-98.4036218913,0.0173,Yes
fcidump.planted_solution_0006.a4b9a6bd-4479-44b2-b172-642f74396781,-113.9731633416,1.2954,-113.9731633416,0.0189,Yes
fcidump.planted_solution_0007.c594d63e-29c7-462a-b385-f70c6d7d8350,-582.1588923786,6.9048,-582.1588923786,0.3509,Yes
fcidump.planted_solution_0008.44060124-8f2d-4a91-80a9-5a29f0f4f716,-117.1341468693,0.8882,-117.1341468693,0.0218,Yes
fcidump.planted_solution_0009.bbbbba1c-868c-45a5-b16c-0c17536e83d8,-1226.2946878373,67.3838,-1226.2946878373,26.4034,Yes
fcidump.planted_solution_0010.eea867d0-285e-462d-94ab-15579c782be7,-534.4214123703,0.1259,-534.4214123703,0.2055,Yes
fcidump.planted_solution_0011.befcf6f0-cfcb-49b7-b661-de48ad8a44c8,-588.2719562041,3.9984,-588.2719562041,0.3477,Yes
fcidump.s_o2_cc-pVDZ.42f8e26e-4707-41e4-8b0a-c099a8a4145c,-547.2047361984,126.1219,-547.2246010116,1.5565,No
fcidump.s_o2_cc-pVTZ.189ad642-9d0f-4d5a-a1b3-1160f515ebf4,-547.4326656349,163.0985,-547.4759537949,27.1178,Yes
fcidump.si2_h6_cc-pVDZ.bdb74fe0-4d88-4e9f-8354-7ff891c21b5b,-580.8257456868,233.9009,-580.9160292131,6.5089,No
fcidump.si_h2_singlet_cc-pVDZ.7fdb7bf4-2eed-4b4f-bf6f-767c7518367d,-289.9408172968,6.0707,-289.9540624037,0.3714,Yes
fcidump.si_h2_singlet_cc-pVQZ.5b274001-6cd6-436f-995f-d460d33688da,-290.0052840422,49.3736,-290.0232165782,21.1920,Yes
fcidump.si_h2_singlet_cc-pVTZ.0534fd24-c760-462e-b288-c3ea9fe721c8,-290.0098694718,10.0112,-290.0272970929,1.8627,Yes
fcidump.si_h4_cc-pVDZ.c37edb04-5163-4d5c-a54e-df5887f0d82e,-290.9294390612,6.2120,-290.9645611152,0.6758,Yes
fcidump.si_h4_cc-pVTZ.e709c0b6-d851-47d2-b72a-f4da8479a772,-291.0057708566,19.8359,-291.0442283809,8.4032,Yes
fcidump.si_o_cc-pVDZ.ab244b36-ab52-4cce-b50a-2b04d8c548e7,-363.7281763495,10.8402,-363.7446729834,0.6388,Yes
fcidump.si_o_cc-pVQZ.80214e7b-2e1f-440f-b9eb-ee9a16ed8398,-363.9409167135,80.7387,-364.0399088044,32.6372,Yes
fcidump.si_o_cc-pVTZ.1b1a93a4-a3cd-424f-87a2-c5a7ae5dbaf7,-363.8789474248,22.4437,-363.9186260270,3.2720,Yes
""".strip()

##############################################################
# 4. Parse the FCIDUMP name => (molecule_name, problem_uuid)
##############################################################
def parse_fcidump_name(fcidump_name: str):
    """
    Expecting pattern like: fcidump.<molecule_name>.<problem_uuid>
    Example: 'fcidump.Cr_0.b8fe08a4-82fe-4636-9812-b1e0666f95b5'
    """
    parts = fcidump_name.split(".")
    if len(parts) < 3:
        # fallback if somehow malformed
        return ("unknown_molecule", "00000000-0000-0000-0000-000000000000")
    return (parts[1], parts[-1])  # molecule_name, problem_uuid

##############################################################
# 5. Build the solution JSON to match the solution.schema.0.0.1.json
##############################################################
def build_solution_dict(problem_instance_uuid, solver_details, energy, run_time_sec):
    """
    Creates the solution dict for a single (energy, runtime) result,
    matching the schema solution.schema.0.0.1.json.
    """
    now_str = datetime.datetime.utcnow().isoformat() + "+00:00"
    solution_uuid = str(uuid.uuid4())
    task_uuid = str(uuid.uuid4())

    solution_dict = {
        "$schema": "https://raw.githubusercontent.com/isi-usc-edu/qb-gsee-benchmark/main/schemas/solution.schema.0.0.1.json",  # or a remote URL if you want
        "solution_uuid": solution_uuid,
        "problem_instance_uuid": problem_instance_uuid,
        "creation_timestamp": now_str,
        "latest_update_timestamp": now_str,  # optional but recommended
        "contact_info": [
            {
                "name": "Mohammad Reza Jangrouei",
                "email": "m.r.jangrouei@gmail.com",
                "institution": "University Of Toronto"
            }
        ],
        "is_resource_estimate": False,
        "solution_data": [
            {
                "task_uuid": task_uuid,
                "energy": float(energy),
                "energy_units": "Hartree",
                "run_time": {
                    "overall_time": {
                        "seconds": float(run_time_sec)
                    }
                },
                # This next block isn't strictly required by the minimal schema, 
                # but you can track CPU time similarly:
                "run_time_cpu": {
                    "overall_time": {
                        "seconds": float(run_time_sec)
                    }
                },
                "solution_details": {}
            }
        ],
        "solver_details": solver_details,
        "digital_signature": None
    }
    return solution_dict

##############################################################
# 6. Main script: parse each line, build solutions,
#    save to CCSD or CCSD(T) directories
##############################################################
def main():
    lines = RAW_DATA.splitlines()
    for line in lines:
        parts = line.split(",")
        if len(parts) != 6:
            print(f"Skipping malformed line:\n  {line}")
            continue

        fcidump_name  = parts[0].strip()
        ccsd_e_str    = parts[1].strip()
        ccsd_time_str = parts[2].strip()
        ccsdt_e_str   = parts[3].strip()
        ccsdt_time_str= parts[4].strip()
        yes_no_str    = parts[5].strip().lower()

        if yes_no_str != "yes":
            # skip entire line
            continue

        molecule_name, problem_uuid = parse_fcidump_name(fcidump_name)

        # Parse CCSD floats
        ccsd_e, ccsd_time = None, None
        if "error" not in ccsd_e_str.lower() and "singular" not in ccsd_e_str.lower():
            if "error" not in ccsd_time_str.lower() and "singular" not in ccsd_time_str.lower():
                try:
                    ccsd_e = float(ccsd_e_str)
                    ccsd_time = float(ccsd_time_str)
                except ValueError:
                    pass  # skip if not valid

        # Parse CCSD(T) floats
        ccsdt_e, ccsdt_time = None, None
        if "error" not in ccsdt_e_str.lower() and "singular" not in ccsdt_e_str.lower():
            if "error" not in ccsdt_time_str.lower() and "singular" not in ccsdt_time_str.lower():
                try:
                    ccsdt_e = float(ccsdt_e_str)
                    ccsdt_time = float(ccsdt_time_str)
                except ValueError:
                    pass

        # --- If CCSD is valid => build solution => save
        if ccsd_e is not None and ccsd_time is not None:
            sol_dict = build_solution_dict(problem_uuid, CCSD_SOLVER_DETAILS, ccsd_e, ccsd_time)
            # naming: solution.<molecule_name>.<problem_uuid>_<solution_uuid>.json
            out_filename = f"solution.{molecule_name}.{problem_uuid}_{sol_dict['solution_uuid']}.json"
            out_path = CCSD_SOLUTIONS_FOLDER / out_filename
            with open(out_path, "w") as f:
                json.dump(sol_dict, f, indent=2)
            print(f"[CCSD] wrote => {out_path}")

        # --- If CCSD(T) is valid => build solution => save
        if ccsdt_e is not None and ccsdt_time is not None:
            sol_dict = build_solution_dict(problem_uuid, CCSDT_SOLVER_DETAILS, ccsdt_e, ccsdt_time)
            out_filename = f"solution.{molecule_name}.{problem_uuid}_{sol_dict['solution_uuid']}.json"
            out_path = CCSDT_SOLUTIONS_FOLDER / out_filename
            with open(out_path, "w") as f:
                json.dump(sol_dict, f, indent=2)
            print(f"[CCSD(T)] wrote => {out_path}")


if __name__ == "__main__":
    main()





