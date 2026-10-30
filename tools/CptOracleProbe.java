/* 开发对照工具；日常 CLI 不依赖 Java 或此文件。使用安装包自己的公开接口。 */
import com.fr.script.Calculator;
import com.fr.report.elementcase.mod.RemoveColumnMOD;
import com.fr.stable.ColumnRow;

public class CptOracleProbe {
    public static void main(String[] args) throws Exception {
        Calculator calculator = Calculator.createCalculator();
        for (String formula : args) {
            System.out.println("FORMULA\t" + formula + "\t"
                + calculator.onAddDeleteColumnOrRow(formula, -1, 0, 1, -1));
        }
        RemoveColumnMOD deletion = new RemoveColumnMOD(1, null);
        for (int column = 0; column < 4; column++) {
            System.out.println("COORD\t" + column + "\t"
                + deletion.mod_columnrow(ColumnRow.valueOf(column, 0)));
        }
    }
}
