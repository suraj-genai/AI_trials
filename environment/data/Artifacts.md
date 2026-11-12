## Final Deliverable Artifact

At the end of the execution of the program, a report is expected to be generated which would detail the allocator structure, metadata protocol and issues in the beginning of the program, the bugs discovered during the analysis, bug rectification process, and score analysis of successful complete runs. 

The report produced must be named `Compilation Report.md`

Produce the document in 4 chapters as follows:
- Chapter 1 Ground Truth value:
This chapter should be a line by line analysis of the instruction file's instruction and then update of the memory block assignments to the individual entities and a collection. This will serve a validation check of the instruction files. The ground truth study is about the resulting block/entity ownership counts and not exact the block location which cannot be determined from the input instruction file.This chapter should be essentially a table as per the following structure.

| Sr.No | Instruction | 1 | 2 |...| 14 | Joint ownerships | Total blocks allocated |
|---|---|--|--| .. |---|---|---|

There should be one table corresponding for one workload instruction file and the filename must be clearly labelled to understand the analysis. 

- Chapter 2 Metadata Analysis
This chapter should detail the final and complete metadata information. Produce the serialized metadata length and the metadata penalty. Then it must produce a decoding of metadata into the ownership information which should be ideally equal to that of the ground truth value for successful execution of the program. 

This analysis basically presents the validation check of the protocol with the ground truth value. This should be presented for each workload and protocol iteration attempted. The code analysis and debugging process must be properly documented. The respective workloads and protocol iteration must be clearly indicated in the report. 

- Chapter 3 Score analysis
This chapter must present the cost score analysis from the metadata and memory movement algorithm presented in the `instruction.md`. This cost score must be calculated for each protocol iteration attempted and must show the trend resulting from the debugging which would be classified as per the individual jobs and their corresponding instruction file names. The total score of all the three jobs must be presented along with whether they are greater or lesser than the marked threshold score in order to be accepted.

- Chapter 4 Debugging analysis
This chapter must highlight the bugs discovered, why they were bugs and how was it rectified. It must highlight the changes brought forth, the details of the protocol being implemented and the reason for the code changes. Since, this section is job independent, this section need not be classified as per the instruction workload files. 